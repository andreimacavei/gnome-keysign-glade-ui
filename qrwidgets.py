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
import logging
from gi.repository import Gtk

from qr_code import QRImage
from barcode_reader import BarcodeReaderGTK

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

        self.reader = BarcodeReaderGTK()
        self.pack_start(self.reader, True, True, 0)