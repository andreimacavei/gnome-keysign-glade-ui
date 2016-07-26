#!/usr/bin/env python

import logging
from gi.repository import Gtk

log = logging.getLogger(__name__)


class QRCodeWidget(Gtk.Box):

    def __init__(self, data='Default String'):
        super(QRCodeWidget, self).__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.data = data
        self.label = Gtk.Label()
        self.draw_qrcode()

        self.pack_start(self.label, True, True, 0)

    def draw_qrcode(self):
        #FIXME replace with qr code draw
        self.label.set_markup('<span size="15000">' + self.data + '</span>')

    def set_data(self, data):
        self.data = data


class QRScannerWidget(Gtk.Box):

    def __init__(self, *args, **kwargs):
        super(QRScannerWidget, self).__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)

        label = Gtk.Label()
        label.set_markup('<span size="10000">Camera feed</span>')

        self.pack_start(label, True, True, 0)