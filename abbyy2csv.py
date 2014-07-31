#!/usr/bin/env python3

from __future__ import (division, print_function)

import argparse
import csv
from lxml import etree


ABBYY_NS = 'http://www.abbyy.com/FineReader_xml/FineReader10-schema-v1.xml'
PAGE = etree.QName(ABBYY_NS, 'page').text
TEXT = etree.QName(ABBYY_NS, 'text').text
LINE = etree.QName(ABBYY_NS, 'line').text
CHAR_PARAMS = etree.QName(ABBYY_NS, 'charParams').text


class Line:
    def __init__(self, baseline, x, y):
        self.baseline = baseline
        self.xy = (x, y)
        self.text = ''


class Processor:
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Convert ABBYY XML files to CSV.')
        parser.add_argument('input', type=argparse.FileType('rb'),
                            help='Input XML file')
        parser.add_argument('output', type=argparse.FileType('w'),
                            help='Output CSV file')
        parser.add_argument('-v', '--verbose', action='store_true',
                            help='Be verbose.')
        args = parser.parse_args()

        self.input = args.input
        self.output = args.output
        self.verbose = args.verbose

        self.pages = 0
        self.lines = []

    def run(self):
        if self.verbose:
            print('Reading file %s ...' % (self.input.name, ))

        content = etree.parse(self.input)
        for elem in content.iter(PAGE):
            self.processPage(elem)

        if self.verbose:
            print('Processed %d pages ...' % (self.pages, ))
            print('Processed %d lines ...' % (len(self.lines), ))

        lines = [(x.baseline, x.xy[0], x.xy[1], x.text) for x in self.lines]
        w = csv.writer(self.output)
        w.writerows(lines)

    def processPage(self, page):
        self.width = int(page.get('width'))
        self.height = int(page.get('height'))
        self.resolution = int(page.get('resolution'))

        if self.height > self.width:
            # Portrait page, probably cover
            return

        for elem in page.iter(TEXT):
            self.processText(elem)

        self.pages += 1

    def processText(self, text):
        orientation = text.get('orientation')
        mirrored = text.get('mirrored') == 'true'
        inverted = text.get('inverted') == 'true'

        if mirrored or inverted:
            return
        if orientation is not None and orientation != 'Normal':
            return

        for elem in text.iter(LINE):
            self.processLine(elem)

    def processLine(self, line):
        baseline = int(line.get('baseline'))
        left = int(line.get('l'))
        top = int(line.get('t'))
        right = int(line.get('r'))
        bottom = int(line.get('b'))

        obj = Line(baseline, left, top)
        self.lines.append(obj)

        for elem in line.iter(CHAR_PARAMS):
            obj.text += elem.text


p = Processor()
p.run()
