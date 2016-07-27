#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import signal
import sys
import time
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG, format='%(name)s (%(levelname)s): %(message)s')

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import (
    GLib,
    GObject,
    Gio,
    Gtk
)

from window import ApplicationWindow


class Application(Gtk.Application):

    version = GObject.Property(type=str,
        flags=GObject.ParamFlags.CONSTRUCT_ONLY|GObject.ParamFlags.READWRITE)

    def __init__(self, **kwargs):
        Gtk.Application.__init__(
            self, application_id=None, **kwargs) #org.gnome.keysign

        self.window = None
        self.log = logging.getLogger()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Create menu action 'quit'
        action = Gio.SimpleAction.new('quit', None)
        action.connect('activate', lambda action, param: self.quit())
        self.add_action(action)

        # Create menu action 'about'
        action = Gio.SimpleAction.new('about', None)
        action.connect('activate', self.on_about)
        self.add_action(action)

        # Set up app menu
        builder = Gtk.Builder.new_from_file("menus.ui")
        self.set_app_menu(builder.get_object("app-menu"))

    def do_activate(self):
        # Set up the app window
        self.window = ApplicationWindow(self)

        self.add_window(self.window)
        # FIXME: The show_all() method is overwritten in ApplicationWindow
        # to show only the app window loaded from builder. I still can't find
        # a solution to have only 1 instance of App Window created.
        # This also bugs the app menu which isn't shown.
        self.window.show_all()

    def do_shutdown(self):
        Gtk.Application.do_shutdown(self)

    def on_about(self, action, param):
        about_dialog = Gtk.AboutDialog(transient_for=self.window, modal=True,
                                       license_type=Gtk.License.GPL_3_0,
                                       authors=['Andrei Macavei', ],
                                       copyright='Copyright © 2016 Andrei Macavei',
                                       logo_icon_name=None,
                                       version=self.version)
        about_dialog.present()

    def on_quit(self, app, param=None):
        self.quit()
