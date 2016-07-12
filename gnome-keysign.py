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


# The modes that app is running
SEND_MODE = 0
RECEIVE_MODE = 1

# The states that the app can have during run-time
SELECT_KEY_STATE = 2
PRESENT_KEY_STATE = 3
ENTER_FPR_STATE = 4
CONFIRM_KEY_STATE = 5

UNKNONW_STATE = -1

def format_listbox_keydata(keydata):
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

def format_details_keydata(keydata):
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


class Application(Gtk.Application):

    version = GObject.Property(type=str,
        flags=GObject.ParamFlags.CONSTRUCT_ONLY|GObject.ParamFlags.READWRITE)

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
        self.notebook1 = self.builder.get_object('notebook1')
        self.notebook2 = self.builder.get_object('notebook2')
        stack.add_titled(self.notebook1, 'notebook1', 'Send')
        stack.add_titled(self.notebook2, 'notebook2', 'Receive')
        stack.show_all()

        self.back_refresh_button = self.builder.get_object("button1")

        # Update the key list with the user's own keys
        listBox = self.builder.get_object('listbox1')
        for key,val in data.items():
            listBox.add(ListBoxRowWithKeyData(key, format_listbox_keydata(val)))

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
        input_text = entryObject.get_text()
        print ("Gtk.Entry text changed: {}".format(input_text))

        if len(input_text) == 40:
            for keyid,val in data.items():
                key = data[keyid]

                if val['fpr'] == entryObject.get_text():
                    keyIdsLabel = self.builder.get_object("key_ids_label")
                    keyIdsLabel.set_markup(key['id'])

                    uidsLabel = self.builder.get_object("uids_label")
                    markup = ""
                    for uid in key['uids']:
                        markup += uid['uid'] + "\n"
                    uidsLabel.set_markup(markup)
                    self.notebook2.next_page()
                    break
            else:
                builder = Gtk.Builder.new_from_file("invalidkeydialog.ui")
                dialog = builder.get_object('invalid_dialog')
                response = dialog.run()
                if response == Gtk.ResponseType.CLOSE:
                    print("WARN dialog closed by clicking CANCEL button")

                dialog.destroy()

    def on_row_activated(self, listBoxObject, listBoxRowObject, builder, *args):
        key = data[listBoxRowObject.keyid]

        keyDetailsLabel = self.builder.get_object("keyDetailsLabel")
        keyDetailsLabel.set_markup(format_details_keydata(key))

        fpr = "<b>{}</b>".format(key['fpr'])
        keyFingerprintLabel = self.builder.get_object("keyFingerprintLabel")
        keyFingerprintLabel.set_markup(fpr)
        keyFingerprintLabel.set_selectable(True)

        self.back_refresh_button.set_image(Gtk.Image.new_from_icon_name("gtk-go-back", Gtk.IconSize.BUTTON))

        self.notebook1.next_page()

    def on_row_selected(self, listBoxObject, listBoxRowObject, builder, *args):
        print ("ListRow selected!Key '{}'' selected".format(listBoxRowObject.keyid))

    def get_app_state(self, mode):
        if mode == SEND_MODE:
            page = self.notebook1.get_current_page()
            return SELECT_KEY_STATE if page == 0 else PRESENT_KEY_STATE

        elif mode == RECEIVE_MODE:
            page = self.notebook2.get_current_page()
            return ENTER_FPR_STATE if page == 0 else CONFIRM_KEY_STATE

        else:
            print ("Wrong app mode")

        return UNKNONW_STATE

    def on_back_refresh_button_clicked(self, buttonObject, *args):
        state = self.get_app_state(SEND_MODE)

        if state == SELECT_KEY_STATE:
            pass

        elif state == PRESENT_KEY_STATE:
            self.back_refresh_button.set_image(Gtk.Image.new_from_icon_name("gtk-refresh",
                    Gtk.IconSize.BUTTON))
            self.notebook1.prev_page()

        else:
            print ("Wrong app state")


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
