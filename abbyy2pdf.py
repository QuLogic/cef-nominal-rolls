#!/usr/bin/env python

from __future__ import (division, print_function)

import argparse
import warnings

from lxml import etree
from reportlab.pdfgen import canvas
from reportlab.rl_config import defaultPageSize
from reportlab.lib.colors import black, white, red, green, blue, yellow


class Processor:
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Convert ABBYY XML files to PDF.')
        parser.add_argument('input', type=argparse.FileType('rb'),
                            help='Input XML file')
        parser.add_argument('output', type=argparse.FileType('wb'),
                            help='Output PDF file')
        parser.add_argument('-v', '--verbose', action='store_true',
                            help='Be verbose.')
        parser.add_argument('-a', '--annotate', action='append', default=[],
                            choices=['all', 'rect', 'line',
                                     'Text', 'Table', 'Picture', 'Barcode',
                                     'Separator', 'SeparatorsBox', 'Checkmark',
                                     'GroupCheckmark'],
                            help='Annotate PDFs by region.')
        args = parser.parse_args()

        self.input = args.input
        self.output = args.output
        self.verbose = args.verbose
        try:
            args.annotate.remove('all')
        except ValueError:
            self.annotate = args.annotate
        else:
            self.annotate = ['rect', 'line',
                             'Text', 'Table', 'Picture', 'Barcode',
                             'Separator', 'SeparatorsBox', 'Checkmark',
                             'GroupCheckmark']
            for x in args.annotate:
                self.annotate.remove(x)

    def run(self):
        self.pdf = canvas.Canvas(self.output, bottomup=0, verbosity=self.verbose)
        self.width, self.height = defaultPageSize
        self.resolution = 72

        content = etree.iterparse(self.input, ('start', 'end'))
        for action, element in content:
            localname = element.tag
            if '}' in localname:
                localname = localname.split('}')[1]
            localname = localname[0].upper() + localname[1:]
            name = action + localname
            if hasattr(self, name):
                func = getattr(self, name)
                func(element)
            else:
                warnings.warn('Unimplemented %s tag: %s' % (action, localname))

        self.pdf.save()


    def startDocument(self, doc):
        version = doc.get('version')
        producer = doc.get('producer')
        pagesCount = int(doc.get('pagesCount', '1'))
        mainLanguage = doc.get('mainLanguage')
        languages = doc.get('languages')
        print(version, producer, pagesCount, mainLanguage, languages)

    def endDocument(self, doc):
        pass


    def startPage(self, page):
        self.width = int(page.get('width'))
        self.height = int(page.get('height'))
        self.resolution = int(page.get('resolution'))
        originCoords = page.get('originalCoords') == 'true'

        width = self.width / self.resolution * 72
        height = self.height / self.resolution * 72

        self.pdf.setPageSize((width, height))

    def endPage(self, page):
        self.pdf.showPage()


    def startBlock(self, block):
        self.blockType = block.get('blockType')
        pageElemId = block.get('pageElemId')
        blockName = block.get('blockName')
        isHidden = block.get('isHidden') == 'true'

        if isHidden:
            return

        self.drawRect(self.blockType, block, blue, optional=True)

    def endBlock(self, block):
        self.blockType = None


    def startRegion(self, region):
        pass

    def endRegion(self, region):
        pass


    def startRect(self, region):
        self.drawRect('rect', region, red)

    def endRect(self, region):
        pass


    def startText(self, text):
        text_id = text.get('id')
        self.orientation = text.get('orientation')
        self.bgColour = int(text.get('backgroundColor', '16777215'))
        self.mirrored = text.get('mirrored') == 'true'
        self.inverted = text.get('inverted') == 'true'
        self.text_obj = self.pdf.beginText()

    def endText(self, text):
        self.pdf.drawText(self.text_obj)
        self.text_obj = None


    def startLine(self, line):
        self.drawRect('line', line, yellow)

    def endLine(self, line):
        pass


    def startFormatting(self, form):
        self.fs = form.get('fs')

        bold = form.get('bold') == 'true'
        italic = form.get('italic') == 'true'
        if bold and italic:
            self.fontname = 'Helvetica-BoldOblique'
        elif bold:
            self.fontname = 'Helvetica-Bold'
        elif italic:
            self.fontname = 'Helvetica-Oblique'
        else:
            self.fontname = 'Helvetica'

        subscript = form.get('subscript') == 'true'
        superscript = form.get('superscript') == 'true'
        smallcaps = form.get('smallcaps') == 'true'
        underline = form.get('underline') == 'true'
        strikeout = form.get('strikeout') == 'true'
        scaling = int(form.get('scaling') or 1000)
        spacing = int(form.get('spacing') or 0)

    def endFormatting(self, form):
        pass


    def startCharParams(self, cp):
        left = int(cp.get('l')) / self.resolution * 72
        top = int(cp.get('t')) / self.resolution * 72
        right = int(cp.get('r')) / self.resolution * 72
        bottom = int(cp.get('b')) / self.resolution * 72
        suspicious = cp.get('suspicious') == 'true'

        self.text_obj.setTextOrigin(left, bottom)
        if self.annotate and suspicious:
            self.text_obj.setFillColor(red)
        else:
            self.text_obj.setFillColor(black)

    def endCharParams(self, cp):
        left = int(cp.get('l')) / self.resolution * 72
        right = int(cp.get('r')) / self.resolution * 72

        text_width = right - left

        if self.fs:
            self.text_obj.setFont(self.fontname, self.fs)
        else:
            fs = 12
            for _i in range(1000):
                width = self.pdf.stringWidth(cp.text, self.fontname, fs)
                if cp.text in 'itr':
                    width *= 1.5
                elif cp.text in 'IT':
                    width *= 1.2
                dw = text_width - width
                if abs(dw) < 1e-6:
                    break
                fs = fs * (1 + dw / width)
            self.text_obj.setFont(self.fontname, fs)

        self.text_obj.textOut(cp.text)


    def drawRect(self, type, elem, colour, optional=False):
        left = elem.get('l')
        top = elem.get('t')
        right = elem.get('r')
        bottom = elem.get('b')
        box = [left, bottom, right, top]

        if type not in self.annotate or (optional and None in box):
            return

        # rect uses (left, bottom, width, height) instead
        box = [int(x) / self.resolution * 72 for x in box]
        box[2] = box[2] - box[0]
        box[3] = box[3] - box[1]

        self.pdf.setStrokeColor(colour)
        self.pdf.rect(*box)


p = Processor()
p.run()

