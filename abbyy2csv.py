#!/usr/bin/env python3
#
# Copyright (C) 2014  Elliott Sales de Andrade
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of version 3 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

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
        parser.add_argument('--algorithm', '-a', default='affinity',
                            choices=['affinity', 'DBSCAN', 'MeanShift'],
                            help='Algorithm to use for clustering.')
        parser.add_argument('--params', '-p',
                            help='Parameters to pass to cluster algorithm.')
        args = parser.parse_args()

        self.input = args.input
        self.output = args.output
        self.verbose = args.verbose

        self.algorithm = args.algorithm
        self.params = {}
        if args.params:
            for p in args.params.split(','):
                key, val = p.split('=')
                try:
                    val = int(val)
                except ValueError:
                    val = float(val)
                except ValueError:
                    pass
                self.params[key] = val

        if self.verbose:
            print('Using %s algorithm with ' % (self.algorithm, ), end='')
            if self.params:
                print(*('%s=%s' % (key, self.params[key])
                        for key in self.params),
                      sep=',', end='.\n')
            else:
                print('default parameters.')

        self.pages = 0
        self.total_lines = 0

    def run(self):
        if self.verbose:
            print('Reading file %s ...' % (self.input.name, ))

        content = etree.parse(self.input)
        self.writer = csv.writer(self.output)
        for elem in content.iter(PAGE):
            self.processPage(elem)

        if self.verbose:
            print('Processed %d pages ...' % (self.pages, ))
            print('Processed %d lines ...' % (self.total_lines, ))

    def analyzeCoverPage(self, objs):
        if self.verbose:
            print('Processing cover page ...')
        lines = [[x.text for x in objs]]
        return lines

    def analyzePage(self, objs):
        if self.verbose:
            print('Processing normal page ...')

        import numpy as np
        from sklearn import cluster
        from sklearn.preprocessing import StandardScaler

        objs = sorted(objs, key=lambda x: x.xy[0])

        X = np.array([[x.baseline] for x in objs], dtype=np.float64)
        X = StandardScaler().fit_transform(X)

        if self.algorithm == 'affinity':
            algorithm = cluster.AffinityPropagation(**self.params)
        elif self.algorithm == 'DBSCAN':
            algorithm = cluster.DBSCAN(**self.params)
        elif self.algorithm == 'MeanShift':
            algorithm = cluster.MeanShift(**self.params)

        y = algorithm.fit_predict(X)

        lines = []
        # ABBYY coordinates are bottom-to-top, so reverse list.
        for i in sorted(set(y), reverse=True):
            index = np.where(y == i)[0]
            line = [x.text for j, x in enumerate(objs) if j in index]
            lines.append(line)

        return lines

    def processPage(self, page):
        self.width = int(page.get('width'))
        self.height = int(page.get('height'))
        self.resolution = int(page.get('resolution'))

        page_objs = []

        for elem in page.iter(TEXT):
            text_objs = self.processText(elem)
            if text_objs:
                page_objs += text_objs

        if self.height > self.width:
            # Portrait page, probably cover
            lines = self.analyzeCoverPage(page_objs)
        else:
            lines = self.analyzePage(page_objs)

        self.writer.writerows(lines)

        self.pages += 1
        self.total_lines += len(lines)

    def processText(self, text):
        orientation = text.get('orientation')
        mirrored = text.get('mirrored') == 'true'
        inverted = text.get('inverted') == 'true'

        if mirrored or inverted:
            return
        if orientation is not None and orientation != 'Normal':
            return

        text_objs = []
        for elem in text.iter(LINE):
            obj = self.processLine(elem)
            text_objs.append(obj)

        return text_objs

    def processLine(self, line):
        baseline = int(line.get('baseline'))
        left = int(line.get('l'))
        top = int(line.get('t'))
        right = int(line.get('r'))
        bottom = int(line.get('b'))

        obj = Line(baseline, left, top)

        for elem in line.iter(CHAR_PARAMS):
            obj.text += elem.text

        return obj


p = Processor()
p.run()
