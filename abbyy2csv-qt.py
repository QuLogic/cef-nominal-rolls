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

from __future__ import (division, print_function, unicode_literals)

import argparse
import csv
import logging
import sys

import sip
API_NAMES = ['QDate', 'QDateTime', 'QString', 'QTextStream', 'QTime', 'QUrl',
             'QVariant']
API_VERSION = 2
for name in API_NAMES:
    sip.setapi(name, API_VERSION)
from PyQt4 import QtCore
from PyQt4 import QtGui

from abbyy2csv import Processor


class QtProcessor(Processor):
    def processResults(self, lines):
        first_row = self.table.rowCount()
        self.table.setRowCount(first_row + len(lines))
        maxcol = max(len(row) for row in lines)
        if maxcol > self.table.columnCount():
            self.table.setColumnCount(maxcol)

        for i, row in enumerate(lines, first_row):
            for j, cell in enumerate(row):
                item = QtGui.QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                self.table.setItem(i, j, item)

        if self.cancelled:
            raise KeyboardInterrupt


class Main(QtGui.QMainWindow):
    def __init__(self, args):
        super(Main, self).__init__()

        self.input = args.input
        self.verbose = args.verbose

        self.row_algorithm = args.row_algorithm
        self.row_params = self.parseAlgParams('row',
                                              args.row_algorithm,
                                              args.row_params)
        self.col_algorithm = args.col_algorithm
        self.col_params = self.parseAlgParams('column',
                                              args.col_algorithm,
                                              args.col_params)

        self.processor = QtProcessor(self.input, None, self.verbose,
                                     self.row_algorithm, self.row_params,
                                     self.col_algorithm, self.col_params)

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

        if self.verbose:
            print('Using %s algorithm for %ss with ' % (algorithm, kind),
                  end='')
            if params:
                print(*('%s=%s' % (key, params[key]) for key in params),
                      sep=',', end='.\n')
            else:
                print('default parameters.')

        return params

    def initUI(self, app):
        self.setWindowTitle('ABBYY to CSV Conversion')
        self.setWindowIcon(QtGui.QIcon.fromTheme('x-office-document'))
        self.resize(800, 680)
        self.show()

        # Status bar for logging
        status = self.statusBar()
        status.setSizeGripEnabled(False)
        logger = logging.getLogger('abbyy2csv')
        handler = QtStatusBarHandler(app, status)
        logger.addHandler(handler)

        self.cancel = QtGui.QPushButton(QtGui.QIcon.fromTheme('process-stop'),
                                        '&Stop', status)
        status.addPermanentWidget(self.cancel)
        self.cancel.setVisible(False)
        self.cancel.clicked.connect(self._cancelProcessing)

        self.alg_tb = toolbar = self.addToolBar('Algorithm')

        # Row algorithm settings
        label = QtGui.QLabel('Rows:', self)
        toolbar.addWidget(label)

        self.row_alg_cb = QtGui.QComboBox(self)
        for alg in ['AffinityPropagation', 'DBSCAN', 'MeanShift']:
            self.row_alg_cb.addItem(alg)
        toolbar.addWidget(self.row_alg_cb)

        self.row_param_sb = QtGui.QDoubleSpinBox(self)
        self.row_param_sb.setDecimals(4)
        self.row_param_sb.setMinimum(0)
        self.row_param_sb.setSpecialValueText('Auto')
        toolbar.addWidget(self.row_param_sb)

        if self.row_algorithm == 'affinity':
            self.row_alg_cb.setCurrentIndex(0)
            self.row_param_sb.setValue(self.row_params.get('damping', 0.5))
        elif self.row_algorithm == 'DBSCAN':
            self.row_alg_cb.setCurrentIndex(1)
            self.row_param_sb.setValue(self.row_params.get('eps', 0.5))
        elif self.row_algorithm == 'MeanShift':
            self.row_alg_cb.setCurrentIndex(2)
            self.row_param_sb.setValue(self.row_params.get('bandwidth', 0))

        self.row_alg_cb.currentIndexChanged.connect(self._setRowAlgorithm)
        self.row_param_sb.valueChanged.connect(self._setRowAlgorithm)

        # Column algorithm settings
        toolbar.addSeparator()
        label = QtGui.QLabel('Columns:', self)
        toolbar.addWidget(label)

        self.col_alg_cb = QtGui.QComboBox(self)
        for alg in ['AffinityPropagation', 'DBSCAN', 'MeanShift']:
            self.col_alg_cb.addItem(alg)
        toolbar.addWidget(self.col_alg_cb)

        self.col_param_sb = QtGui.QDoubleSpinBox(self)
        self.col_param_sb.setDecimals(4)
        self.col_param_sb.setMinimum(0)
        self.col_param_sb.setSpecialValueText('Auto')
        toolbar.addWidget(self.col_param_sb)

        if self.col_algorithm == 'affinity':
            self.col_alg_cb.setCurrentIndex(0)
            self.col_param_sb.setValue(self.col_params.get('damping', 0.5))
        elif self.col_algorithm == 'DBSCAN':
            self.col_alg_cb.setCurrentIndex(1)
            self.col_param_sb.setValue(self.col_params.get('eps', 0.5))
        elif self.col_algorithm == 'MeanShift':
            self.col_alg_cb.setCurrentIndex(2)
            self.col_param_sb.setValue(self.col_params.get('bandwidth', 0))

        self.col_alg_cb.currentIndexChanged.connect(self._setColAlgorithm)
        self.col_param_sb.valueChanged.connect(self._setColAlgorithm)

        # Exit button
        exitAction = QtGui.QAction(QtGui.QIcon.fromTheme('application-exit'),
                                   'Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(QtGui.qApp.quit)
        toolbar = self.addToolBar('Exit')
        toolbar.addAction(exitAction)

        # Main table view
        self.table = QtGui.QTableWidget(self)
        self.setCentralWidget(self.table)
        self.processor.table = self.table

        # Timer for user actions
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.processXML)
        self.timer.start(0)

    def _setRowAlgorithm(self, unused):
        index = self.row_alg_cb.currentIndex()
        value = self.row_param_sb.value()

        if index == 0:
            self.processor.row_algorithm = 'affinity'
            param = 'damping'
        elif index == 1:
            self.processor.row_algorithm = 'DBSCAN'
            param = 'eps'
        elif index == 2:
            self.processor.row_algorithm = 'MeanShift'
            param = 'bandwidth'

        if value:
            self.processor.row_params = {param: value}
        else:
            self.processor.row_params = {}

        self.timer.start(1000)

    def _setColAlgorithm(self, unused):
        index = self.col_alg_cb.currentIndex()
        value = self.col_param_sb.value()

        if index == 0:
            self.processor.col_algorithm = 'affinity'
            param = 'damping'
        elif index == 1:
            self.processor.col_algorithm = 'DBSCAN'
            param = 'eps'
        elif index == 2:
            self.processor.col_algorithm = 'MeanShift'
            param = 'bandwidth'

        if value:
            self.processor.col_params = {param: value}
        else:
            self.processor.col_params = {}

        self.timer.start(1000)

    def _cancelProcessing(self):
        self.processor.cancelled = True

    def processXML(self):
        self.alg_tb.setEnabled(False)
        self.cancel.setVisible(True)
        self.processor.cancelled = False
        self.input.seek(0)
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)

        try:
            self.processor.run()
        except KeyboardInterrupt:
            # Processing cancelled. Ignore.
            pass

        for i in range(min(5, self.table.columnCount())):
            self.table.setColumnHidden(i, True)
        self.statusBar().clearMessage()
        self.cancel.setVisible(False)
        self.alg_tb.setEnabled(True)


class QtStatusBarHandler(logging.Handler):
    def __init__(self, app, status):
        logging.Handler.__init__(self)
        self.app = app
        self.status = status

    def emit(self, record):
        s = self.format(record) + '\n'
        self.status.showMessage(s)
        self.app.processEvents()


parser = argparse.ArgumentParser(
    description='GUI program to convert ABBYY XML files to CSV.')
parser.add_argument('input', type=argparse.FileType('rb'),
                    help='Input XML file')
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
args, leftover = parser.parse_known_args()

app = QtGui.QApplication(leftover)
m = Main(args)
m.initUI(app)
sys.exit(app.exec_())
