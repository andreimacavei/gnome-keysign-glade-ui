#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import signal
import sys
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG, format='%(name)s (%(levelname)s): %(message)s')

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
    'key3' : {'id':'2048R/ED8312A2 2010-04-08',
              'fpr':'6011B4B032D3DED8312A2BEFDD433DCF8956D0D3',
              'uids':[
                    {'uid':'John Who john.who@test.com',
                     'sigs':['ED8312A2']
                    }
                    ],
              'expire':'2016-07-14',
              'nsigs':1
             },
    'key4' : {'id':'2048R/D32DFCFB 2013-01-01',
              'fpr':'CEDF933BF372D3D32DFCFBB870D356F7ECD46CF2',
              'uids':[
                    {'uid':'Educated Foo edu.foo@test.com',
                     'sigs':['D32DFCFB','6FB8DCCE', '8956D0D3']
                    }
                    ],
              'expire':'2020-05-05',
              'nsigs':3
             },
}

# The states that the app can have during run-time
UNKNOWN_STATE = 0
SELECT_KEY_STATE = 1
PRESENT_KEY_STATE = 2
ENTER_FPR_STATE = 3
DOWNLOAD_KEY_STATE = 4
CONFIRM_KEY_STATE = 5

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
    result = ""
    for uid in keydata['uids']:
        result += "{}\n".format(uid['uid'])

    return result

def clean_fingerprint(fpr):
    res_fpr = ''.join(fpr.split())
    return res_fpr.upper()

def is_valid_fingerprint(fpr):
    cleaned_fpr = clean_fingerprint(fpr)
    if len(cleaned_fpr) != 40:
        return False

    return True


def format_fpr(fpr):
    res_fpr = ""
    for i in range(0, len(fpr), 4):
        res_fpr += fpr[i:i+4]
        if i != 0 and (i+4) % 20 == 0:
            res_fpr += "\n"
        else:
            res_fpr += " "
    res_fpr = res_fpr.rstrip()
    return res_fpr


class ListBoxRowWithKeyData(Gtk.ListBoxRow):

    def __init__(self, keydata):
        super(Gtk.ListBoxRow, self).__init__()
        self.data = keydata

        label = Gtk.Label()
        label.set_markup(format_listbox_keydata(self.data))
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
            self.builder.add_from_file("send.ui")
            self.builder.add_from_file("receive.ui")
        except:
            self.log.exception("ui file not found")
            sys.exit()

        self.builder.connect_signals(self)
        self.window = None
        self.log = logging.getLogger()

        self.state = None
        self.last_state = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        self.stack = self.builder.get_object('stack1')
        self.stack2 = self.builder.get_object('stack2')
        self.stack3 = self.builder.get_object('stack3')
        self.stack.add_titled(self.stack2, 'stack2', 'Send')
        self.stack.add_titled(self.stack3, 'stack3', 'Receive')
        self.stack.show_all()

        self.back_refresh_button = self.builder.get_object("button1")

        # Update the key list with the user's own keys
        listBox = self.builder.get_object('listbox1')
        for keydata in data.values():
            listBox.add(ListBoxRowWithKeyData(keydata))

        listBox.connect('row-activated', self.on_row_activated, self.builder)
        listBox.connect('row-selected', self.on_row_selected, self.builder)

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

        self.add_window(self.window)
        self.window.show_all()

    def get_app_state(self):
        return self.state

    def update_app_state(self, new_state=None):
        self.last_state = self.state

        if new_state:
            self.state = new_state
        else:
            visible_top_child = self.stack.get_visible_child()
            if visible_top_child == self.stack2:
                page = self.stack2.get_visible_child_name()
                self.state = SELECT_KEY_STATE if page == 'page0' else PRESENT_KEY_STATE
            elif visible_top_child == self.stack3:
                page = self.stack3.get_visible_child_name()
                if page == 'page0':
                    self.state = ENTER_FPR_STATE
                elif page == 'page1':
                    self.state = DOWNLOAD_KEY_STATE
                else:
                    self.state = CONFIRM_KEY_STATE
            else:
                self.state = UNKNOWN_STATE
                self.log.error("Unknown application state!")

        self.log.debug("App state changed! Last state: {}. Current state: {}".format(self.last_state, self.state))

    def on_top_stack_notify(self, stackObject, paramString, *args):
        self.update_app_state()
        # We can advance in a page and then switch to the other
        # stack page so we need to update the top left button
        self.update_back_refresh_button_icon()

    def update_back_refresh_button_icon(self):
        state = self.state
        last_state = self.last_state

        if last_state and last_state != state:
            if state == SELECT_KEY_STATE or state == ENTER_FPR_STATE:
                self.back_refresh_button.set_image(Gtk.Image.new_from_icon_name("gtk-refresh",
                            Gtk.IconSize.BUTTON))
            elif state in (PRESENT_KEY_STATE, DOWNLOAD_KEY_STATE, CONFIRM_KEY_STATE):
                self.back_refresh_button.set_image(Gtk.Image.new_from_icon_name("gtk-go-back",
                            Gtk.IconSize.BUTTON))
            else:
                self.log.error("Update button icon failed. Unknown application state!")

    def on_back_refresh_button_clicked(self, buttonObject, *args):
        state = self.get_app_state()

        if state == SELECT_KEY_STATE:
            self.update_app_state(SELECT_KEY_STATE)
        elif state == PRESENT_KEY_STATE:
            self.stack2.set_visible_child_name('page0')
            self.update_app_state(SELECT_KEY_STATE)
        elif state == ENTER_FPR_STATE:
            self.update_app_state(ENTER_FPR_STATE)
        elif state == DOWNLOAD_KEY_STATE:
            self.stack3.set_visible_child_name('page0')
            self.update_app_state(ENTER_FPR_STATE)
        elif state == CONFIRM_KEY_STATE:
            self.stack3.set_visible_child_name('page0')
            self.update_app_state(ENTER_FPR_STATE)
        else:
            self.log.error("Unknown application state!")

        self.update_back_refresh_button_icon()

    def on_text_changed(self, entryObject, *args):
        cleaned_fpr = clean_fingerprint(entryObject.get_text())
        self.log.debug("Gtk.Entry text changed: {}".format(cleaned_fpr))

        if is_valid_fingerprint(cleaned_fpr):
            for keyid,val in data.items():
                key = data[keyid]

                if val['fpr'] == cleaned_fpr:

                    keyIdsLabel = self.builder.get_object("key_ids_label")
                    keyIdsLabel.set_markup(key['id'])

                    uidsLabel = self.builder.get_object("uids_label")
                    markup = ""
                    for uid in key['uids']:
                        markup += uid['uid'] + "\n"
                    uidsLabel.set_markup(markup)

                    self.stack3.set_visible_child_name('page1')
                    self.update_app_state(DOWNLOAD_KEY_STATE)
                    self.update_back_refresh_button_icon()

                    break
            else:
                builder = Gtk.Builder.new_from_file("invalidkeydialog.ui")
                dialog = builder.get_object('invalid_dialog')
                response = dialog.run()
                if response == Gtk.ResponseType.CLOSE:
                    self.log.debug("WARN dialog closed by clicking CLOSE button")
                    pass

                dialog.destroy()

    def on_row_activated(self, listBoxObject, listBoxRowObject, builder, *args):
        key = listBoxRowObject.data

        keyidLabel = self.builder.get_object("keyidLabel")
        keyid_str = "{0}".format(key['id'])
        keyidLabel.set_markup(keyid_str)

        uidsLabel = self.builder.get_object("uidsLabel")
        uidsLabel.set_markup(format_details_keydata(key))

        fpr = format_fpr(key['fpr'])
        keyFingerprintLabel = self.builder.get_object("keyFingerprintLabel")
        keyFingerprintLabel.set_markup('<span size="20000">' + fpr + '</span>')
        keyFingerprintLabel.set_selectable(True)

        self.stack2.set_visible_child_name('page1')
        self.update_app_state(PRESENT_KEY_STATE)
        self.update_back_refresh_button_icon()

    def on_row_selected(self, listBoxObject, listBoxRowObject, builder, *args):
        self.log.debug("ListRow selected!Key '{}'' selected".format(listBoxRowObject.data['id']))

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
