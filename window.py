#!/usr/bin/env python

import logging
import signal
import sys
import time

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import (
    GLib,
    GObject,
    Gio,
    Gtk
)

import utils

# The states that the app can have during run-time
UNKNOWN_STATE = 0
SELECT_KEY_STATE = 1
PRESENT_KEY_STATE = 2
ENTER_FPR_STATE = 3
DOWNLOAD_KEY_STATE = 4
CONFIRM_KEY_STATE = 5
SIGN_KEY_STATE = 6


class ListBoxRowWithKeyData(Gtk.ListBoxRow):

    def __init__(self, keydata):
        super(Gtk.ListBoxRow, self).__init__()
        self.data = keydata

        label = Gtk.Label()
        label.set_markup(utils.format_listbox_keydata(self.data))
        self.add(label)


class ApplicationWindow(Gtk.ApplicationWindow):

    __gsignals__ = {
        'valid-fingerprint': (GObject.SIGNAL_RUN_LAST, None,
                         # Hm, this is a str for now, but ideally
                         # it'd be the full key object
                         (GObject.TYPE_PYOBJECT,)),
        'sign-key-confirmed': (GObject.SIGNAL_RUN_LAST, None,
                         # Hm, this is a str for now, but ideally
                         # it'd be the full key object
                         (GObject.TYPE_PYOBJECT,GObject.TYPE_PYOBJECT)),
    }

    def __init__(self, app, **kwargs):
        Gtk.ApplicationWindow.__init__(self, application=app, **kwargs)

        self.app = app
        self.builder = Gtk.Builder()
        try:
            self.builder.add_from_file("applicationwindow.ui")
            self.builder.add_from_file("send.ui")
            self.builder.add_from_file("receive.ui")
        except:
            self.log.exception("ui file not found")
            sys.exit()

        self.builder.connect_signals(self)

        self.log = logging.getLogger()
        self.state = None
        self.last_state = None
        self.cancel_flag = False
        self.key = None

        self.appwindow = self.builder.get_object("applicationwindow1")

        self.connect('valid-fingerprint', self.on_valid_fingerprint)
        self.connect('sign-key-confirmed', self.on_sign_key_confirmed)

        self.stack = self.builder.get_object('stack1')
        self.stack2 = self.builder.get_object('stack2')
        self.stack3 = self.builder.get_object('stack3')

        self.stack.add_titled(self.stack2, 'stack2', 'Send')
        self.stack.add_titled(self.stack3, 'stack3', 'Receive')
        self.stack.show_all()

        self.back_refresh_button = self.builder.get_object("button1")
        self.error_download_label = self.builder.get_object("error_download_label")

        self.spinner1 = self.builder.get_object("spinner1")
        self.spinner2 = self.builder.get_object("spinner2")
        self.succes_fail_signing_label = self.builder.get_object("succes_fail_signing_label")

        # Update the key list with the user's own keys
        self.listbox = self.builder.get_object('listbox1')
        keys = utils.get_secret_keys()
        for keydata in keys.values():
            self.listbox.add(ListBoxRowWithKeyData(keydata))

        self.listbox.connect('row-activated', self.on_row_activated, self.builder)
        self.listbox.connect('row-selected', self.on_row_selected, self.builder)



    def do_show_all(self):
        self.appwindow.show_all()

    def update_key_list(self):
        #FIXME do not remove rows, but update data
        for listrow in self.listbox:
            self.listbox.remove(listrow)

        keys = utils.get_secret_keys()
        for keydata in keys.values():
            self.listbox.add(ListBoxRowWithKeyData(keydata))
        self.listbox.show_all()

    def download_key(self, key):
        if not self.cancel_flag:
            self.stack3.set_visible_child_name('page2')
            self.update_app_state(CONFIRM_KEY_STATE)
            self.update_back_refresh_button_icon()

        self.spinner1.stop()
        self.cancel_flag = False
        return False

    def on_valid_fingerprint(self, app, key):
        self.log.info("Signal emitted: valid-fingerprint: {}".format(key['id']))
        download_time = 3
        GLib.timeout_add_seconds(download_time, self.download_key, key, priority=GLib.PRIORITY_DEFAULT)

    def sign_key(self, key, uids):
        if not self.cancel_flag:
            self.succes_fail_signing_label.set_markup("Key succesfully signed!")
            self.succes_fail_signing_label.show()

        self.spinner2.stop()
        self.cancel_flag = False
        return False

    def on_sign_key_confirmed(self, app, key, uids):
        self.log.info("Signal emitted: sign-key-confirmed: {}".format(key['id']))

        uids_repr = '\n'.join([uid['uid'] for uid in uids])
        uids_signed_label = self.builder.get_object("uids_signed_label")
        uids_signed_label.set_markup(uids_repr)

        signing_time = 2
        GLib.timeout_add_seconds(signing_time, self.sign_key, key, uids, priority=GLib.PRIORITY_DEFAULT)

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
                elif page == 'page2':
                    self.state = CONFIRM_KEY_STATE
                else:
                    self.state = SIGN_KEY_STATE
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
            elif state in (PRESENT_KEY_STATE, DOWNLOAD_KEY_STATE, CONFIRM_KEY_STATE, SIGN_KEY_STATE):
                self.back_refresh_button.set_image(Gtk.Image.new_from_icon_name("gtk-go-back",
                            Gtk.IconSize.BUTTON))
            else:
                self.log.error("Update button icon failed. Unknown application state!")

    def on_back_refresh_button_clicked(self, buttonObject, *args):
        state = self.get_app_state()

        if state == SELECT_KEY_STATE:
            self.update_app_state(SELECT_KEY_STATE)
            self.update_key_list()
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
        elif state == SIGN_KEY_STATE:
            self.stack3.set_visible_child_name('page2')
            self.update_app_state(CONFIRM_KEY_STATE)
        else:
            self.log.error("Unknown application state!")

        self.update_back_refresh_button_icon()

    def on_text_changed(self, entryObject, *args):
        cleaned_fpr = utils.clean_fingerprint(entryObject.get_text())
        self.log.debug("Gtk.Entry text changed: {}".format(cleaned_fpr))

        if utils.is_valid_fingerprint(cleaned_fpr):
            keys = utils.get_secret_keys()
            for keyid,val in keys.items():
                key = keys[keyid]

                if val['fpr'] == cleaned_fpr:
                    keyIdsLabel = self.builder.get_object("key_ids_label")
                    keyIdsLabel.set_markup(key['id'])

                    uidsLabel = self.builder.get_object("uids_label")
                    markup = ""
                    for uid in key['uids']:
                        markup += uid['uid'] + "\n"
                    uidsLabel.set_markup(markup)

                    self.error_download_label.hide()
                    self.spinner1.start()

                    self.stack3.set_visible_child_name('page1')
                    self.update_app_state(DOWNLOAD_KEY_STATE)
                    self.update_back_refresh_button_icon()

                    self.key = key
                    self.emit('valid-fingerprint', key)
                    break
            else:
                builder = Gtk.Builder.new_from_file("invalidkeydialog.ui")
                dialog = builder.get_object('invalid_dialog')
                dialog.set_transient_for(self.window)
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
        uidsLabel.set_markup(utils.format_details_keydata(key))

        fpr = utils.format_fpr(key['fpr'])
        keyFingerprintLabel = self.builder.get_object("keyFingerprintLabel")
        keyFingerprintLabel.set_markup('<span size="20000">' + fpr + '</span>')
        keyFingerprintLabel.set_selectable(True)

        self.stack2.set_visible_child_name('page1')
        self.update_app_state(PRESENT_KEY_STATE)
        self.update_back_refresh_button_icon()

    def on_row_selected(self, listBoxObject, listBoxRowObject, builder, *args):
        self.log.debug("ListRow selected!Key '{}'' selected".format(listBoxRowObject.data['id']))

    def on_cancel_download_button_clicked(self, buttonObject, *args):
        self.log.debug("Cancel download button clicked.")
        self.cancel_flag = True
        self.error_download_label.show()
        self.spinner1.stop()

    def on_confirm_button_clicked(self, buttonObject, *args):
        self.log.debug("Confirm sign button clicked.")

        self.succes_fail_signing_label.hide()
        self.spinner2.start()

        self.stack3.set_visible_child_name('page3')
        self.update_app_state(SIGN_KEY_STATE)
        self.update_back_refresh_button_icon()

        # FIXME user should be able to choose which UIDs he wants to sign
        uids_to_sign = self.key['uids']
        self.emit('sign-key-confirmed', self.key, uids_to_sign)

    def on_cancel_signing_button_clicked(self, buttonObject, *args):
        self.log.debug("Cancel signing button clicked.")
        self.cancel_flag = True
        self.succes_fail_signing_label.set_markup('Key signing was interrupted!')
        self.succes_fail_signing_label.show()
        self.spinner2.stop()

    def on_redo_button_clicked(self, buttonObject, *args):
        self.log.debug("Redo button clicked.")
        pass

    def on_delete_window(self, *args):
        # Gtk.main_quit(*args)
        # It seems that calling Gtk.main_quit doesn't work as expected
        self.app.on_quit(self)
