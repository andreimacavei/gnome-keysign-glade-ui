#!/usr/bin/env python
#    Copyright 2016 Andrei Macavei <andrei.macavei89@gmail.com>
#
#    This file is part of GNOME Keysign.
#
#    GNOME Keysign is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    GNOME Keysign is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with GNOME Keysign.  If not, see <http://www.gnu.org/licenses/>.

import glob
from keysign import __version__ as version

from setuptools import setup, find_packages
import setuptools.command.build_py


class BuildPyCommand(setuptools.command.build_py.build_py):
    def run(self):
        setuptools.command.build_py.build_py.run(self)


if __name__ == '__main__':
    maintainers = 'Andrei Macavei, '
    maintainers_emails = ('andrei.macavei89@gmail.com')

    data_files = [
        ('share/keysign/ui', glob.glob("keysign/widgets/*.ui")),
    ]

    setup(
        name = 'gnome-keysign',
        version = version,
        description = 'OpenPGP key signing helper',
        author = maintainers,
        author_email = maintainers_emails,
        # maintainer=maintainers,
        # maintainer_email=maintainers_emails,
        packages = [
            'keysign',
            'keysign.network',
            'keysign.widgets',
            ],
        py_modules = [
            'monkeysign.msgfmt',
            'monkeysign.translation',
            'monkeysign.gpg',
        ],
        package_dir={'monkeysign': 'monkeysign/monkeysign'},
        #package_dir={'keysign': 'keysign'},
        #package_data={'keysign': ['data/']},
        data_files=data_files,
        include_package_data = True,
        #scripts = ['gnome-keysign.py'],
        install_requires=[
            'qrcode',
            'requests>=2.6',
            ],
        license='GPLv3+',
        # long_description=open('README.rst').read(),

        entry_points = {
            # 'console_scripts': [
            #    'keysign = keysign.main'
            # ],
            'gui_scripts': [
                'gnome-keysign = keysign:main',
            ],
        },
        cmdclass = {
            'build_py': BuildPyCommand,
        },
        classifiers = [
            'Development Status :: 4 - Beta',

            'Environment :: X11 Applications :: GTK',

            'Intended Audience :: Developers',
            'Intended Audience :: System Administrators',
            'Intended Audience :: End Users/Desktop',
            'Intended Audience :: Information Technology',
            'Intended Audience :: Legal Industry',
            'Intended Audience :: Telecommunications Industry',

            'License :: OSI Approved :: GNU General Public License (GPL)',
            'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',

            'Natural Language :: English',

            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.7',
            # We're still lacking support for 3
            #'Programming Language :: Python :: 3',

            'Operating System :: POSIX :: Linux',

            'Topic :: Desktop Environment',
            'Topic :: Communications :: Email',
            'Topic :: Multimedia :: Video :: Capture',
            'Topic :: Security :: Cryptography',
            'Topic :: Software Development :: Libraries :: Python Modules',
            ]
        )