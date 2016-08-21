#!/usr/bin/env python

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
        ('share/keysign/ui', glob.glob("data/*.ui")),
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
            'keysign'
            ],
        #package_dir={'keysign': 'keysign'},
        #package_data={'keysign': ['data/']},
        data_files=data_files,
        include_package_data = True,
        #scripts = ['gnome-keysign.py'],
        install_requires=[
            'qrcode',
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