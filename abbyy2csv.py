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
        parser.add_argument('--row-algorithm', '-r', default='affinity',
                            choices=['affinity', 'DBSCAN', 'MeanShift'],
                            help='Algorithm to use for row clustering.')
        parser.add_argument('--col-algorithm', '-c', default='affinity',
                            choices=['affinity', 'DBSCAN', 'MeanShift'],
                            help='Algorithm to use for column clustering.')
        parser.add_argument('--row-params', '-rp',
                            help='Parameters to use in row algorithm.')
        parser.add_argument('--col-params', '-cp',
                            help='Parameters to use in column algorithm.')
        args = parser.parse_args()

        self.input = args.input
        self.output = args.output
        self.verbose = args.verbose

        self.row_algorithm = args.row_algorithm
        self.row_params = self.parseAlgParams('row',
                                              args.row_algorithm,
                                              args.row_params)
        self.col_algorithm = args.col_algorithm
        self.col_params = self.parseAlgParams('column',
                                              args.col_algorithm,
                                              args.col_params)

        self.pages = 0
        self.total_lines = 0

    def parseAlgParams(self, kind, algorithm, arg_params):
        params = {}
        if arg_params:
            for p in arg_params.split(','):
                key, val = p.split('=')
                try:
                    val = int(val)
                except ValueError:
                    val = float(val)
                except ValueError:
                    pass
                params[key] = val

        if self.verbose:
            print('Using %s algorithm for %ss with ' % (algorithm, kind),
                  end='')
            if params:
                print(*('%s=%s' % (key, params[key]) for key in params),
                      sep=',', end='.\n')
            else:
                print('default parameters.')

        return params

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

        if self.row_algorithm == 'affinity':
            row_algorithm = cluster.AffinityPropagation(**self.row_params)
        elif self.row_algorithm == 'DBSCAN':
            row_algorithm = cluster.DBSCAN(**self.row_params)
        elif self.row_algorithm == 'MeanShift':
            row_algorithm = cluster.MeanShift(**self.row_params)

        if self.col_algorithm == 'affinity':
            col_algorithm = cluster.AffinityPropagation(**self.col_params)
        elif self.col_algorithm == 'DBSCAN':
            col_algorithm = cluster.DBSCAN(**self.col_params)
        elif self.col_algorithm == 'MeanShift':
            col_algorithm = cluster.MeanShift(**self.col_params)

        Y = np.array([[y.baseline] for y in objs], dtype=np.float64)
        rows = row_algorithm.fit_predict(Y)

        X = np.array([[x.xy[0]] for x in objs], dtype=np.float64)
        col_algorithm.fit(X)

        lines = []
        # ABBYY coordinates are bottom-to-top, so reverse list.
        for i in sorted(set(rows), reverse=True):
            index = np.where(rows == i)[0]
            line_objs = [x for j, x in enumerate(objs) if j in index]

            X = np.array([[x.xy[0]] for x in line_objs], dtype=np.float64)
            cols = col_algorithm.predict(X)

            line = []
            for col, obj in zip(cols, line_objs):
                while len(line) < col:
                    line.append(None)
                line.append(obj.text)

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
