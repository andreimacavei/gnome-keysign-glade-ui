#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import signal
import sys
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG, format='%(name)s (%(levelname)s): %(message)s')

from gi.repository import GLib

from keysign.app import Application

def main():
    app = Application()

    try:
        GLib.unix_signal_add_full(GLib.PRIORITY_HIGH, signal.SIGINT, lambda *args : app.quit(), None)
    except AttributeError:
        pass

    exit_status = app.run(None)
    return exit_status

if __name__ == '__main__':
    sys.exit(main())
