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

import csv
import os


try:
    os.mkdir(os.path.join('web', 'Nominal_Rolls'))
except OSError:
    pass

for dirpath, dirnames, filenames in os.walk('Nominal Rolls'):
    if dirpath == 'Nominal Rolls':
        with open('web/index.html', 'rt') as f:
            text = f.readlines()

        with open('web/index.html', 'wt') as f:
            for line in text:
                f.write(line)
                if '## Browse' in line:
                    break
            for name in dirnames:
                path = os.path.join(dirpath.replace(' ', '_'),
                                    name.replace(' ', '_'))
                f.write('  * [' + name + '](' + path + ')\n')

    else:
        index = os.path.join('web',
                             dirpath.replace(' ', '_'),
                             'index.html')
        with open(index, 'wt') as f:
            f.write('---\n')
            f.write('title: ' + dirpath.split('/')[-1] + '\n')
            f.write('---\n')
            f.write('\n')

            for name in sorted(dirnames):
                path = name.replace(' ', '_')
                f.write('  * [' + name + '](' + path + ')\n')

            for name in sorted(filenames):
                if name[-3:] != 'csv':
                    continue

                path = name[:-3].replace(' ', '_') + 'html'
                f.write('  * [' + name[:-4] + '](' + path + ')\n')

    for name in dirnames:
        path = os.path.join('web',
                            dirpath.replace(' ', '_'),
                            name.replace(' ', '_'))
        try:
            os.mkdir(path)
        except OSError:
            # already exists
            pass

    for name in filenames:
        if name[-3:] == 'csv':
            orig_path = os.path.join(dirpath, name)
            ncols = 0
            lines = []
            with open(orig_path, 'rt') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    ncols = max(ncols, len(row))
                    clean_row = [x.replace('|', '&#124;') for x in row]
                    lines.append(row)

            new_path = os.path.join('web',
                                    dirpath.replace(' ', '_'),
                                    name.replace(' ', '_'))
            new_path = new_path[:-3]
            new_path += 'md'
            with open(new_path, 'wt') as f:
                f.write('---\n')
                f.write('title: ' + name[:-4] + '\n')
                f.write('---\n')
                f.write('\n')

                if not ncols:
                    continue

                f.write('{% raw %}\n')
                f.write('| ' * ncols + '|\n')
                f.write('| --- ' * ncols + '|\n')
                for row in lines:
                    f.write('| ')
                    f.write(' | '.join(row))
                    f.write(' |\n')
                f.write('{% endraw %}\n')
