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
import logging
from lxml import etree

import numpy as np
from sklearn import cluster


ABBYY_NS = 'http://www.abbyy.com/FineReader_xml/FineReader10-schema-v1.xml'
PAGE = etree.QName(ABBYY_NS, 'page').text
TEXT = etree.QName(ABBYY_NS, 'text').text
LINE = etree.QName(ABBYY_NS, 'line').text
CHAR_PARAMS = etree.QName(ABBYY_NS, 'charParams').text


class Line:
    def __init__(self, baseline, left, top, right, bottom):
        self.baseline = baseline
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.text = ''


class Processor:
    def __init__(self, input, output, verbose,
                 row_algorithm, row_params, col_algorithm, col_params):

        self.input = input
        self.output = output
        self.logger = logging.getLogger(__name__)
        if verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.WARNING)

        self.row_algorithm = row_algorithm
        self.row_params = row_params
        self.col_algorithm = col_algorithm
        self.col_params = col_params

        self.pages = 0
        self.total_lines = 0

    def run(self):
        self.logger.debug('Reading file %s ...' % (self.input.name, ))

        content = etree.parse(self.input)
        self.writer = csv.writer(self.output)
        for elem in content.iter(PAGE):
            self.processPage(elem)

        self.logger.info('Processed %d pages ...' % (self.pages, ))
        self.logger.info('Processed %d lines ...' % (self.total_lines, ))

    def analyzeCoverPage(self, objs):
        '''
        Analyze a portrait page, which is probably a cover.
        '''
        self.logger.debug('Processing cover page ...')
        lines = [[self.pages + 1, None, None, None, None] +
                 [x.text for x in objs]]
        return lines

    def analyzePage(self, objs):
        '''
        Analyze a normal page and produce lines of cells`.
        '''
        self.logger.debug('Processing normal page ...')

        rows, num_rows, fuzzy_rows = self.getSortedRowClusters(objs)
        cols, num_cols, fuzzy_cols = self.getSortedColumnClusters(objs)
        self.logger.debug('    Unique rows & columns: %d %d' % (
            num_rows, num_cols))
        if fuzzy_rows:
            self.logger.warning('    Row results fuzzy; '
                                'check nothing is missing.')
        if fuzzy_cols:
            self.logger.warning('    Column results fuzzy; '
                                'check nothing is missing.')

        lines = []
        for index in rows:
            line_objs = [x for j, x in enumerate(objs) if j in index]
            line_cols = np.take(cols, index)

            left = min(x.left for x in line_objs)
            top = min(x.top for x in line_objs)
            right = max(x.right for x in line_objs)
            bottom = max(x.bottom for x in line_objs)

            line = [self.pages + 1, left, top, right, bottom]
            for col, obj in zip(line_cols, line_objs):
                if col == -1:
                    continue

                while len(line) < col + 5:
                    line.append(None)
                line.append(obj.text)

            lines.append(line)

        return lines

    def getSortedRowClusters(self, objs):
        '''
        Determine row clusters and their order.

        Clusters that create rows are determined by the user-specified
        algorithm. They are then sorted by location, and lists of indices for
        each cluster are returned in order.
        '''
        if self.row_algorithm == 'affinity':
            algorithm = cluster.AffinityPropagation(**self.row_params)
        elif self.row_algorithm == 'DBSCAN':
            algorithm = cluster.DBSCAN(**self.row_params)
        elif self.row_algorithm == 'MeanShift':
            algorithm = cluster.MeanShift(**self.row_params)

        Y = np.array([[y.baseline] for y in objs], dtype=np.float64)
        rows = algorithm.fit_predict(Y)

        if self.row_algorithm == 'affinity':
            # Here, samples are the found location, so just sort directly.
            row_set = set(rows)

            def ordered_clusters():
                # ABBYY coordinates are bottom-to-top, so reverse list.
                for i in sorted(row_set, reverse=True):
                    yield np.where(rows == i)[0]

            return ordered_clusters(), len(row_set), False

        elif self.row_algorithm == 'DBSCAN':
            # Here, samples are labelled, so go back and find the original
            # locations.
            fuzzy = -1 in rows
            num_clusters = len(set(rows)) - (1 if fuzzy else 0)
            clusters = []
            cluster_centres = np.empty(num_clusters)
            for i in range(num_clusters):
                index = np.where(rows == i)
                clusters.append(index[0])
                cluster_centres[i] = np.mean(np.take(Y, index))

            ordered_clusters = (clust for centre, clust in
                                sorted(zip(cluster_centres, clusters)))
            return ordered_clusters, num_clusters, fuzzy

        elif self.row_algorithm == 'MeanShift':
            # Here, samples are labelled, but cluster locations are provided.
            fuzzy = -1 in rows
            num_clusters = len(set(rows)) - (1 if fuzzy else 0)
            clusters = []
            for i in range(num_clusters):
                index = np.where(rows == i)
                clusters.append(index[0])

            ordered_clusters = (clust for centre, clust in
                                sorted(zip(algorithm.cluster_centers_,
                                           clusters)))
            return ordered_clusters, num_clusters, fuzzy

    def getSortedColumnClusters(self, objs):
        '''
        Determine column clusters and their order.

        Clusters that create columns are determined by the user-specified
        algorithm. They are then sorted by location, and the indices are
        returned.
        '''
        if self.col_algorithm == 'affinity':
            algorithm = cluster.AffinityPropagation(**self.col_params)
        elif self.col_algorithm == 'DBSCAN':
            algorithm = cluster.DBSCAN(**self.col_params)
        elif self.col_algorithm == 'MeanShift':
            algorithm = cluster.MeanShift(**self.col_params)

        X = np.array([[x.left] for x in objs], dtype=np.float64)
        cols = algorithm.fit_predict(X)

        if self.col_algorithm == 'affinity':
            # Here, samples are the found location, so just sort directly.
            sorted_locations = sorted(set(cols))
            num_clusters = len(sorted_locations)

            sorted_col_indices = np.empty(len(objs))
            for i, loc in enumerate(sorted_locations):
                index = np.where(cols == loc)[0]
                sorted_col_indices[index] = i

            fuzzy = False

        elif self.col_algorithm == 'DBSCAN':
            # Here, samples are labelled, so go back and find the original
            # locations.
            fuzzy = -1 in cols
            num_clusters = len(set(cols)) - (1 if fuzzy else 0)
            cluster_centres = np.empty(num_clusters)
            clusters = []
            for i in range(num_clusters):
                index = np.where(cols == i)
                clusters.append(index[0])
                cluster_centres[i] = np.mean(np.take(X, index))
            indices = np.argsort(cluster_centres)

            sorted_col_indices = -np.ones(len(objs))
            for i, j in enumerate(indices):
                index = clusters[j]
                sorted_col_indices[index] = i

        elif self.col_algorithm == 'MeanShift':
            # Here, samples are labelled, but cluster locations are provided.
            fuzzy = -1 in cols
            num_clusters = len(set(cols)) - (1 if fuzzy else 0)
            clusters = []
            for i in range(num_clusters):
                index = np.where(cols == i)[0]
                clusters.append(index)
            indices = np.argsort(algorithm.cluster_centers_)

            sorted_col_indices = -np.ones(len(objs))
            for i, j in enumerate(indices):
                index = clusters[j]
                sorted_col_indices[index] = i

        return sorted_col_indices, num_clusters, fuzzy

    def processPage(self, page):
        '''
        Process a page and output results to CSV file.
        '''
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

        self.logger.info('    Max columns: %d' % (max(len(x) for x in lines)))
        self.logger.info('    New rows: %d' % (len(lines)))
        self.pages += 1
        self.total_lines += len(lines)

    def processText(self, text):
        '''
        Process a text block.
        '''
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
        '''
        Process a line of text.
        '''
        baseline = int(line.get('baseline'))
        left = int(line.get('l'))
        top = int(line.get('t'))
        right = int(line.get('r'))
        bottom = int(line.get('b'))

        obj = Line(baseline, left, top, right, bottom)

        for elem in line.iter(CHAR_PARAMS):
            obj.text += elem.text

        return obj


class Main:
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

        logging.basicConfig(level=logging.DEBUG if args.verbose else None)

        row_algorithm = args.row_algorithm
        row_params = self.parseAlgParams('row',
                                         args.row_algorithm,
                                         args.row_params)
        col_algorithm = args.col_algorithm
        col_params = self.parseAlgParams('column',
                                         args.col_algorithm,
                                         args.col_params)

        self.processor = Processor(args.input, args.output, args.verbose,
                                   row_algorithm, row_params,
                                   col_algorithm, col_params)

    def parseAlgParams(self, kind, algorithm, arg_params):
        '''
        Parse user-specified parameters for a clustering algorithm.
        '''
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

        msg = 'Using %s algorithm for %ss with ' % (algorithm, kind)
        if params:
            msg += ','.join(*('%s=%s' % (key, params[key]) for key in params))
        else:
            msg += 'default parameters.'
        logging.info(msg)

        return params

    def run(self):
        self.processor.run()

if __name__ == '__main__':
    m = Main()
    m.run()
