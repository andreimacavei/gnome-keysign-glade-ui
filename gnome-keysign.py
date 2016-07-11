#!/usr/bin/env python
# -*- coding: utf-8 -*-

import signal
import sys

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import (
    GLib,
    GObject,
    Gio,
    Gtk
)

data = {
    'key1' : {'id':'2048R/ED8312A2 2014-04-08',
              'fpr':'BEFDD433DCF8956D0D36011B4B032D3DED8312A2',
              'uids':[
                    {'uid':'John Doe john.doe@test.com',
                     'sigs':['ED8312A2', '6FB8DCCE']
                    },
                    {'uid':'John Foo (Test Key) john.foe@test.com',
                     'sigs':['ED8312A2']
                    }
                    ],
              'expire':'2016-12-12',
              'nsigs':3
             },
    'key2' : {'id':'2048R/D32DFCFB 2015-08-20',
              'fpr':'B870D356F7ECD46CF2CEDF933BF372D3D32DFCFB',
              'uids':[
                    {'uid':'Foo Bar foo.bar@test.com',
                     'sigs':['D32DFCFB','6FB8DCCE']
                    }
                    ],
              'expire':'2016-05-20',
              'nsigs':2
             },
}


def formatListboxKeydata(keydata):
    keyid = keydata['id']
    uids = keydata['uids']
    expire = keydata['expire']
    nsigs = keydata['nsigs']

    result = "<b>{0}</b>\t\t\t{1}\n".format(keyid, nsigs)
    for uid in uids:
        result += "{}\n".format(uid['uid'])
    result += "\n"
    result += "<small>Expires {}</small>".format(expire)

    return result

def formatDetailsKeydata(keydata):
    result = "{0}\n".format(keydata['id'])
    for uid in keydata['uids']:
        result += "{}\n".format(uid['uid'])

    return result


class ListBoxRowWithKeyData(Gtk.ListBoxRow):

    def __init__(self, keyid, keydata):
        super(Gtk.ListBoxRow, self).__init__()
        self.keyid = keyid
        self.data = keydata

        label = Gtk.Label()
        label.set_markup(keydata)
        self.add(label)


class KeyPresentPage:

    def __init__(self, keyid, builder):
        self.builder = builder

        key = data[keyid]

        self.keyDetailsLabel = self.builder.get_object("keyDetailsLabel")
        self.keyDetailsLabel.set_markup(formatDetailsKeydata(key))

        fpr = "<b>{}</b>".format(key['fpr'])
        self.keyFingerprintLabel = self.builder.get_object("keyFingerprintLabel")
        self.keyFingerprintLabel.set_markup(fpr)


class Application(Gtk.Application):

    version = GObject.Property(type=str, flags=GObject.ParamFlags.CONSTRUCT_ONLY|GObject.ParamFlags.READWRITE)

    def __init__(self):
        Gtk.Application.__init__(
            self, application_id=None) #org.gnome.keysign

        self.builder = Gtk.Builder()
        try:
            self.builder.add_from_file("applicationwindow.ui")
            self.builder.add_from_file("sendkey.ui")
            self.builder.add_from_file("receivekey.ui")
        except:
            print("ui file not found")
            sys.exit()

        self.builder.connect_signals(self)
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        stack = self.builder.get_object('stack1')
        notebook1 = self.builder.get_object('notebook1')
        box2 = self.builder.get_object('box2')
        stack.add_titled(notebook1, 'notebook1', 'Send')
        stack.add_titled(box2, 'box2', 'Receive')
        stack.show_all()

        # Update the key list with the user's own keys
        listBox = self.builder.get_object('listbox1')
        for key,val in data.items():
            listBox.add(ListBoxRowWithKeyData(key, formatListboxKeydata(val)))

        listBox.connect('row-activated', self.on_row_activated, self.builder)
        listBox.connect('row-selected', self.on_row_selected, self.builder)

        self.headerBar = self.builder.get_object('headerbar1')
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
        self.window = self.builder.get_object("applicationwindow1")
        self.window.set_titlebar(self.headerBar)

        self.add_window(self.window)
        self.window.show_all()

    def on_text_changed(self, entryObject, *args):
        print ("Gtk.Entry text changed: {}".format(entryObject.get_text()))
        for key,val in data.items():
            if val['fpr'] == entryObject.get_text():
                keyConfirmWindow = KeyConfirmWindow(key)
                keyConfirmWindow.show_confirm_window()
                break

    def on_row_activated(self, listBoxObject, listBoxRowObject, builder, *args):
        keyPresentPage = KeyPresentPage(listBoxRowObject.keyid, builder)
        notebook = listBoxObject.get_parent()
        notebook.next_page()

    def on_row_selected(self, listBoxObject, listBoxRowObject, builder, *args):
        print ("ListRow selected!Key '{}'' selected".format(listBoxRowObject.keyid))

    def on_delete_window(self, *args):
        # Gtk.main_quit(*args)
        # It seems that calling Gtk.main_quit doesn't work as expected
        self.on_quit(self)

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


class KeyConfirmWindow:

    def __init__(self, keyid):
        self.builder = Gtk.Builder()
        self.builder.add_from_file("KeyConfirmWindow.glade")
        self.builder.connect_signals(self)

        self.confirm_window = self.builder.get_object("confirm_window")
        self.invalid_dialog = self.builder.get_object("invalid_dialog")

        headerBar = self.builder.get_object("headerbar1")
        self.confirm_window.set_titlebar(headerBar)

        self.key = data[keyid]

    def show_confirm_window(self):
        keyIdsLabel = self.builder.get_object("key_ids_label")
        keyIdsLabel.set_markup(self.key['id'])

        uidsLabel = self.builder.get_object("uids_label")
        markup = ""
        for uid in self.key['uids']:
            markup += uid['uid'] + "\n"
        uidsLabel.set_markup(markup)

        self.confirm_window.show_all()

    def show_invalid_dialog(self):
        pass

    def on_delete_key_confirm_window(self, *args):
        keyConfirmWindow = args[0]
        keyConfirmWindow.close()

    def on_delete_invalid_dialog(self, *args):
        pass


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
