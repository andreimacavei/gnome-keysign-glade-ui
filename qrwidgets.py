#!/usr/bin/env python

import logging
from gi.repository import Gtk

from QRcode import QRImage

log = logging.getLogger(__name__)


class QRCodeWidget(Gtk.Box):

    def __init__(self, data='Default String'):
        super(QRCodeWidget, self).__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.qrcode = QRImage(data)
        self.qrcode.props.margin = 10

        self.pack_start(self.qrcode, True, True, 0)

    def set_data(self, data):
        self.qrcode.data = data


class QRScannerWidget(Gtk.Box):

    def __init__(self, *args, **kwargs):
        super(QRScannerWidget, self).__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)

        label = Gtk.Label()
        label.set_markup('<span size="10000">Camera feed</span>')

        self.pack_start(label, True, True, 0)