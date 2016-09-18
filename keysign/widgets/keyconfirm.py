#!/usr/bin/env python
# encoding: utf-8
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

import signal
import sys
import argparse
import logging
import os

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GLib
from gi.repository import GObject


if  __name__ == "__main__" and __package__ is None:
    logging.getLogger().error("You seem to be trying to execute " +
                              "this script directly which is discouraged. " +
                              "Try python -m instead.")
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.sys.path.insert(0, parent_dir)
    import keysign
    #mod = __import__('keysign')
    #sys.modules["keysign"] = mod
    __package__ = str('keysign')


from keysign.gpgmh import get_usable_keys
from keysign.app import format_key_header, format_uidslist

log = logging.getLogger(__name__)



class PreSignWidget(Gtk.VBox):
    """A widget for obtaining a key fingerprint.

    The fingerprint can be obtain by inserting it into
    a text entry, or by scanning a barcode with the
    built-in camera.
    """

    __gsignals__ = {
        str('sign-key-confirmed'): (GObject.SIGNAL_RUN_LAST, None,
                                    (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self, pattern=None):
        super(PreSignWidget, self).__init__()
        thisdir = os.path.dirname(os.path.abspath(__file__))
        builder = Gtk.Builder.new_from_file(os.path.join(thisdir, 'receive.ui'))
        widget = builder.get_object('box10')
        widget.reparent(self)

        confirm_btn = builder.get_object("confirm_sign_button")
        confirm_btn.connect("clicked", self.on_confirm_button_clicked)

        self.key = get_usable_keys(pattern=pattern)[0]

        keyIdsLabel = builder.get_object("key_ids_label")
        keyIdsLabel.set_markup(format_key_header(self.key.fingerprint))

        uidsLabel = builder.get_object("uids_label")
        markup = format_uidslist(self.key.uidslist)
        uidsLabel.set_markup(markup)


    def on_confirm_button_clicked(self, buttonObject, *args):
        self.emit('sign-key-confirmed', self.key, *args)



class PreSignApp(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super(PreSignApp, self).__init__(*args, **kwargs)
        self.connect('activate', self.on_activate)
        self.psw = None

        self.log = logging.getLogger(__name__)

    def on_activate(self, app):
        window = Gtk.ApplicationWindow()
        window.set_title("Key Pre Sign Widget")
        # window.set_size_request(600, 400)

        if not self.psw:
            self.psw = PreSignWidget()

        self.psw.connect('sign-key-confirmed', self.on_sign_key_confirmed)
        window.add(self.psw)

        window.show_all()
        self.add_window(window)

    def on_sign_key_confirmed(self, keyPreSignWidget, *args):
        self.log.debug ("Sign key confirmed!")

    def run(self, args):
        if not args:
            args = [""]
        self.psw = PreSignWidget(args[0])
        super(PreSignApp, self).run()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)
    app = PreSignApp()
    app.run(sys.argv[1:])
