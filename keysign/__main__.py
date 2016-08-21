#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging, sys

from .__init__ import main



if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr,
        level=logging.DEBUG,
        format='%(name)s (%(levelname)s): %(message)s')
    sys.exit(main())