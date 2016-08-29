#!/usr/bin/env python

import logging
import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GObject  # for __gsignals__
from gi.repository import GLib  # for markup_escape_text

if  __name__ == "__main__" and __package__ is None:
    logging.getLogger().error("You seem to be trying to execute " +
                              "this script directly which is discouraged. " +
                              "Try python -m instead.")
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.sys.path.insert(0, parent_dir)
    os.sys.path.insert(0, os.path.join(parent_dir, 'monkeysign'))
    import keysign
    #mod = __import__('keysign')
    #sys.modules["keysign"] = mod
    __package__ = str('keysign')

from .gpgmh import get_usable_keys
from .gpgmh import get_usable_secret_keys

log = logging.getLogger(__name__)

class ListBoxRowWithKey(Gtk.ListBoxRow):

    def __init__(self, key):
        super(ListBoxRowWithKey, self).__init__()
        self.key = key

        s = self.format(key)
        label = Gtk.Label(s, use_markup=True, xalign=0)
        self.add(label)


    @classmethod
    def format_uid(cls, uid):
        fmt  = "{name}\t<i>{email}</i>\t<small>{expiry}</small>"

        d = {k: GLib.markup_escape_text("{}".format(v))
             for k,v in uid._asdict().items()}
        log.info("Formatting UID %r", d)
        s = fmt.format(**d)
        log.info("Formatted UID: %r", s)
        return s


    @classmethod
    def format(cls, key):
        fmt  = "{created} "
        fmt  = "<b>{fingerprint}</b>\n"
        fmt += "\n".join((cls.format_uid(uid) for uid in key.uidslist))
        fmt += "\n<small>Expires {expiry}</small>"

        d = {k: GLib.markup_escape_text("{}".format(v))
             for k,v in key._asdict().items()}
        log.info("Formatting key %r", d)
        s = fmt.format(**d)
        log.info("Formatted key: %r", s)
        return s


class KeyListWidget(Gtk.HBox):
    __gsignals__ = {
        str('row-activated'): (GObject.SIGNAL_RUN_LAST, None,
                               (ListBoxRowWithKey.__gtype__,)),
        str('row-selected'): (GObject.SIGNAL_RUN_LAST, None,
                               (ListBoxRowWithKey.__gtype__,)),
    }

    def __init__(self, pattern=None, public=False):
        super(KeyListWidget, self).__init__()

        thisdir = os.path.dirname(os.path.abspath(__file__))
        builder = Gtk.Builder.new_from_file(os.path.join(thisdir, 'send.ui'))
        stack = builder.get_object('box2')
        stack.reparent(self)
        #stack._builder = builder

        self.listbox = builder.get_object("keys_listbox")
        self.listbox.connect('row-activated', self.on_row_activated)
        self.listbox.connect('row-selected', self.on_row_selected)

        if public:
            keys = get_usable_keys(pattern=pattern)
        else:
            keys =  get_usable_secret_keys(pattern=pattern)

        for key in keys:
            lbr = ListBoxRowWithKey(key)
            self.listbox.add(lbr)

    def on_row_activated(self, keylistwidget, row):
        self.emit('row-activated', row)

    def on_row_selected(self, keylistwidget, row):
        self.emit('row-selected', row)



class App(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)
        self.connect('activate', self.on_activate)
        self.kpw = None

    def on_activate(self, app):
        window = Gtk.ApplicationWindow()
        window.set_title("Glade Widgets")
        window.set_size_request(600, 400)
        #window.add(self.builder.get_object('stack2'))
        if not self.kpw:
            self.kpw = KeyListWidget()
        self.kpw.connect('row-activated', self.on_row_activated)
        self.kpw.connect('row-selected', self.on_row_selected)
        window.add(self.kpw)

        window.show_all()
        self.add_window(window)

    def on_row_activated(self, keylistwidget, row):
        self.get_windows()[0].get_window().beep()
        print ("Row activated! %r" % (row,))

    def on_row_selected(self, keylistwidget, row):
        print ("Row selected! %r" % (row,))

    def run(self, args):
        if not args:
            args = [""]
        self.kpw = KeyListWidget(args[0])
        super(App, self).run()

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)
    app = App()
    app.run(sys.argv[1:])