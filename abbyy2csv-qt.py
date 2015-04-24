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
import os
import shelve
import sys

import sip
API_NAMES = ['QDate', 'QDateTime', 'QString', 'QTextStream', 'QTime', 'QUrl',
             'QVariant']
API_VERSION = 2
for name in API_NAMES:
    sip.setapi(name, API_VERSION)
from PyQt4 import QtCore
from PyQt4 import QtGui
import popplerqt4

from abbyy2csv import Processor, TextObject


RESOLUTION = 300  # Output from ABBYY, probably PDF resolution, too...


class QtProcessor(Processor):
    def processResults(self, lines):
        first_row = self.table.rowCount()
        self.table.setRowCount(first_row + len(lines))
        maxcol = max(len(row) for row in lines)
        if maxcol > self.table.columnCount():
            self.table.setColumnCount(maxcol)

        for i, row in enumerate(sorted(lines), first_row):
            for j, obj in enumerate(row):
                if isinstance(obj, TextObject):
                    contents = str(obj.text)
                elif isinstance(obj, int):
                    contents = str(obj)
                else:
                    contents = None
                item = QtGui.QTableWidgetItem(contents)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setData(QtCore.Qt.UserRole, obj)
                self.table.setItem(i, j, item)

        self.app.processEvents()
        if self.cancelled:
            raise KeyboardInterrupt


class Main(QtGui.QMainWindow):
    def __init__(self, args):
        super(Main, self).__init__()

        self.verbose = args.verbose

        self.row_algorithm = args.row_algorithm
        self.row_params = self.parseAlgParams('row',
                                              args.row_algorithm,
                                              args.row_params)
        self.col_algorithm = args.col_algorithm
        self.col_params = self.parseAlgParams('column',
                                              args.col_algorithm,
                                              args.col_params)

        self.processor = QtProcessor(None, None, self.verbose,
                                     self.row_algorithm, self.row_params,
                                     self.col_algorithm, self.col_params)

        # Load cached parameters
        self.data = shelve.open('cache.db', writeback=True)
        files = list(self.data.keys())
        for dirpath, dirnames, filenames in os.walk('Nominal Rolls'):
            for name in filenames:
                if name[-3:] == 'xml':
                    basename = os.path.join(dirpath, name[:-4])
                    if basename not in self.data:
                        self.data[basename] = {
                            'row_algorithm': self.row_algorithm,
                            'row_params': self.row_params,
                            'col_algorithm': self.col_algorithm,
                            'col_params': self.col_params
                        }
                        files += [basename]
        self.files = sorted(files)
        try:
            basename = args.start[:-4]
            self.file_index = self.files.index(basename)
        except (TypeError, ValueError):
            self.file_index = 0

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

    def closeEvent(self, e):
        self.data.close()

    def saveResult(self):
        '''
        Save result to CSV and cache parameters in DB.
        '''

        basename = self.files[self.file_index]

        with open(basename + '.csv', 'w') as output:
            writer = csv.writer(output)
            rows = self.table.rowCount()
            cols = self.table.columnCount()
            for i in range(rows):
                line = []
                for j in range(cols):
                    item = self.table.item(i, j)
                    if item:
                        line.append(item.text())
                    else:
                        line.append(None)
                while line and line[-1] is None:
                    line.pop()
                writer.writerow(line)

        self.data[basename] = {
            'row_algorithm': self.row_algorithm,
            'row_params': self.row_params,
            'col_algorithm': self.col_algorithm,
            'col_params': self.col_params
        }

    def initUI(self, app):
        basename = self.files[self.file_index]
        self.setWindowTitle('%s - ABBYY to CSV Conversion' % (basename, ))
        self.setWindowIcon(QtGui.QIcon.fromTheme('accessories-text-editor'))
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

        # File navigation, Save and Exit buttons
        self.action_tb = toolbar = self.addToolBar('Actions')

        saveAction = QtGui.QAction(QtGui.QIcon.fromTheme('document-save'),
                                   'Save', self)
        saveAction.setShortcut('Ctrl+S')
        saveAction.triggered.connect(self.saveResult)
        toolbar.addAction(saveAction)

        self.prevAction = QtGui.QAction(QtGui.QIcon.fromTheme('go-previous'),
                                        'Previous', self)
        self.prevAction.setShortcut('Ctrl+P')
        self.prevAction.triggered.connect(self._prevFile)
        toolbar.addAction(self.prevAction)

        self.nextAction = QtGui.QAction(QtGui.QIcon.fromTheme('go-next'),
                                        'Next', self)
        self.nextAction.setShortcut('Ctrl+N')
        self.nextAction.triggered.connect(self._nextFile)
        toolbar.addAction(self.nextAction)

        exitAction = QtGui.QAction(QtGui.QIcon.fromTheme('application-exit'),
                                   'Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(QtGui.qApp.quit)
        toolbar.addAction(exitAction)

        # Main table view
        self.table = QtGui.QTableWidget(self)
        self.processor.table = self.table
        self.table.itemSelectionChanged.connect(self._refreshSelection)

        # PDF viewer pane
        self.pdfview = ScalableImage(self)
        self.pdfscale = 1.0

        splitter = QtGui.QSplitter(QtCore.Qt.Vertical, self)
        splitter.addWidget(self.table)
        splitter.addWidget(self.pdfview)
        self.setCentralWidget(splitter)

        # Timer for user actions
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.processXML)

        self.processor.app = app
        self._refreshFile()

    def _refreshFile(self):
        self.prevAction.setEnabled(self.file_index != 0)
        self.nextAction.setEnabled(self.file_index != len(self.files) - 1)

        basename = self.files[self.file_index]
        self.setWindowTitle('%s - ABBYY to CSV Conversion' % (basename, ))

        self.pdf = doc = popplerqt4.Poppler.Document.load(basename + '.pdf')
        doc.setRenderHint(popplerqt4.Poppler.Document.Antialiasing)
        doc.setRenderHint(popplerqt4.Poppler.Document.TextAntialiasing)
        self.pdfview.setText('Nothing Selected')
        self.pdfview.setWidgetResizable(True)

        self.timer.start(1000)

    def _prevFile(self):
        self.file_index = max(self.file_index - 1, 0)
        self._refreshFile()

    def _nextFile(self):
        self.file_index = min(self.file_index + 1, len(self.files))
        self._refreshFile()

    def _refreshSelection(self):
        selected = self.table.selectedIndexes()

        rows = [item.row() for item in selected]
        pages = [int(self.table.item(row, 0).text()) for row in rows]

        page = self.pdf.page(pages[0] - 1)
        image = page.renderToImage(RESOLUTION, RESOLUTION)

        painter = QtGui.QPainter()
        painter.begin(image)

        painter.setPen(QtCore.Qt.red)
        for row in rows:
            try:
                top = float(self.table.item(row, 1).text())
                left = float(self.table.item(row, 2).text())
                bottom = float(self.table.item(row, 3).text())
                right = float(self.table.item(row, 4).text())
            except ValueError:
                continue
            painter.drawRect(left, top, right - left, bottom - top)

        half_yellow = QtGui.QColor(QtCore.Qt.yellow)
        half_yellow.setAlphaF(0.5)
        midx = midy = total_points = 0
        for item in selected:
            obj = item.data(QtCore.Qt.UserRole)
            if not isinstance(obj, TextObject):
                continue

            painter.fillRect(obj.left, obj.top,
                             obj.right - obj.left, obj.bottom - obj.top,
                             half_yellow)

            midx += obj.left + obj.right
            midy += obj.top + obj.bottom
            total_points += 1

        painter.end()

        if total_points:
            midx /= (total_points * 2)
            midy /= (total_points * 2)

        self.pdfview.setImage(image)
        self.pdfview.ensureVisible(midx, midy)

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
        if index == 1:
            self.processor.row_params['min_samples'] = 3

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
        self.action_tb.setEnabled(False)
        self.cancel.setVisible(True)
        self.processor.cancelled = False
        self.processor.pages = 0
        self.processor.total_lines = 0
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)

        basename = self.files[self.file_index]
        with open(basename + '.xml', 'rb') as f:
            self.processor.input = f
            try:
                self.processor.run()
            except KeyboardInterrupt:
                # Processing cancelled. Ignore.
                pass
            self.processor.input = None

        for i in range(min(5, self.table.columnCount())):
            self.table.setColumnHidden(i, True)
        self.statusBar().clearMessage()
        self.cancel.setVisible(False)
        self.alg_tb.setEnabled(True)
        self.action_tb.setEnabled(True)


class ScalableImage(QtGui.QScrollArea):
    def __init__(self, *args, **kwargs):
        super(ScalableImage, self).__init__(*args, **kwargs)

        self.image = QtGui.QLabel(self)
        self.image.setAlignment(QtCore.Qt.AlignCenter)
        self.image.setScaledContents(True)
        self.image.setSizePolicy(QtGui.QSizePolicy.Ignored,
                                 QtGui.QSizePolicy.Ignored)
        self.setWidget(self.image)

        self.scale = 1.0

    def setText(self, text):
        self.image.setText(text)
        self.setWidgetResizable(True)
        self.scale = 1.0

    def setImage(self, image):
        pix = QtGui.QPixmap.fromImage(image)
        self.image.setPixmap(pix)
        self.setWidgetResizable(False)
        self.image.resize(self.scale * self.image.pixmap().size())

    def ensureVisible(self, x, y):
        super(ScalableImage, self).ensureVisible(x * self.scale,
                                                 y * self.scale)

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            if event.delta() > 0:
                self._scaleImage(1.25)
            else:
                self._scaleImage(0.8)
        else:
            super(ScalableImage, self).wheelEvent(event)

    def _scaleImage(self, factor):
        new_scale = self.scale * factor
        if new_scale > 3 or new_scale < 0.01:
            return

        self.scale = new_scale
        self.image.resize(self.scale * self.image.pixmap().size())

        self._adjustScrollBar(self.horizontalScrollBar(), factor)
        self._adjustScrollBar(self.verticalScrollBar(), factor)

    def _adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value() +
                               ((factor - 1) * scrollBar.pageStep() / 2)))


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
parser.add_argument('-v', '--verbose', action='store_true',
                    help='Be verbose.')
parser.add_argument('-s', '--start',
                    help='Starting input XML file. Must be in Nominal Rolls '
                         'directory.')
parser.add_argument('--row-algorithm', '-r', default='affinity',
                    choices=['affinity', 'DBSCAN', 'MeanShift'],
                    help='Default algorithm to use for row clustering.')
parser.add_argument('--col-algorithm', '-c', default='affinity',
                    choices=['affinity', 'DBSCAN', 'MeanShift'],
                    help='Default algorithm to use for column clustering.')
parser.add_argument('--row-params', '-rp',
                    help='Default parameters to use in row algorithm.')
parser.add_argument('--col-params', '-cp',
                    help='Default parameters to use in column algorithm.')
args, leftover = parser.parse_known_args()

app = QtGui.QApplication(['ABBYY2CSV'] + leftover)
m = Main(args)
m.initUI(app)
sys.exit(app.exec_())
