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

from datetime import date, datetime
from qrcode import QRCodeWidget, QRScannerWidget

try:
    import keysign.gpgmh
except ImportError as e:
    print e
    import gpgmh


# The states that the app can have during runtime
UNKNOWN_STATE = 0
SELECT_KEY_STATE = 1
PRESENT_KEY_STATE = 2
ENTER_FPR_STATE = 3
DOWNLOAD_KEY_STATE = 4
CONFIRM_KEY_STATE = 5
SIGN_KEY_STATE = 6

#FIXME: remove the temporary keyword args after updating Key class
#with length and creation_time fields
def format_key_header(fpr, length='2048', creation_time=None):
    if creation_time == None:
        creation_time = datetime.strptime('01011970', "%d%m%Y").date()
    try:
        creation = date.fromtimestamp(float(creation_time))
    except TypeError as e:
        # This might be the case when the creation_time is already a timedate
        creation = creation_time

    key_header = ("{}/{} {}".format(length, fpr[-8:], creation))
    return key_header

def format_uidslist(uidslist):
    result = ""
    for uid in uidslist:
        uidstr = str(uid).replace('<', '').replace('>', '')
        result += ("{}\n".format(uidstr))

    return result

def format_listbox_key(key):
    key_header = format_key_header(key.fingerprint)
    nsigs = 1 #FIXME: do we need this propr?

    result = ("{}\t\t\t{}\n".format(key_header, nsigs))
    result += format_uidslist(key.uidslist)

    if key.expiry:
        result += ("\n<small>Expires {}</small>".format(date.fromtimestamp(float(key.expiry))))
    else:
        result += ("\n<small>No expiration date</small>")
    return result

def clean_fingerprint(fpr):
    res_fpr = ''.join(fpr.split())
    return res_fpr.upper()

def is_valid_fingerprint(fpr):
    cleaned_fpr = clean_fingerprint(fpr)
    if len(cleaned_fpr) != 40:
        return False

    return True


def format_fingerprint(fpr):
    res_fpr = ""
    for i in range(0, len(fpr), 4):
        res_fpr += fpr[i:i+4]
        if i != 0 and (i+4) % 20 == 0:
            res_fpr += "\n"
        else:
            res_fpr += " "
    res_fpr = res_fpr.rstrip()
    return res_fpr


class ListBoxRowWithKey(Gtk.ListBoxRow):

    def __init__(self, key):
        super(Gtk.ListBoxRow, self).__init__()
        self.key = key

        label = Gtk.Label()
        label.set_markup(format_listbox_key(self.key))
        self.add(label)


class Application(Gtk.Application):

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

        self.connect('valid-fingerprint', self.on_valid_fingerprint)
        self.connect('sign-key-confirmed', self.on_sign_key_confirmed)

        self.state = None
        self.last_state = None
        self.key = None
        self.timeout_id = 0

    def do_startup(self):
        Gtk.Application.do_startup(self)

        self.stack = self.builder.get_object('stack1')
        self.stack2 = self.builder.get_object('stack2')
        self.stack3 = self.builder.get_object('stack3')
        self.stack.add_titled(self.stack2, 'stack2', 'Send')
        self.stack.add_titled(self.stack3, 'stack3', 'Receive')
        self.stack.show_all()

        self.qrscanner = QRScannerWidget()
        scan_frame = self.builder.get_object("scan_frame")
        scan_frame.add(self.qrscanner)

        self.back_refresh_button = self.builder.get_object("button1")
        self.error_download_label = self.builder.get_object("error_download_label")
        self.spinner1 = self.builder.get_object("spinner1")
        self.spinner2 = self.builder.get_object("spinner2")
        self.succes_fail_signing_label = self.builder.get_object("succes_fail_signing_label")
        # Update the key list with the user's own keys
        self.listbox = self.builder.get_object('listbox1')
        keys = gpgmh.get_usable_secret_keys()
        for key in keys:
            self.listbox.add(ListBoxRowWithKey(key))

        self.listbox.connect('row-activated', self.on_row_activated, self.builder)
        self.listbox.connect('row-selected', self.on_row_selected, self.builder)

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

    def update_key_list(self):
        #FIXME do not remove rows, but update data
        for listrow in self.listbox:
            self.listbox.remove(listrow)

        keys = gpgmh.get_usable_secret_keys()
        for key in keys:
            self.listbox.add(ListBoxRowWithKey(key))
        self.listbox.show_all()

    def download_key(self, key):
        self.stack3.set_visible_child_name('page2')
        self.update_app_state(CONFIRM_KEY_STATE)
        self.update_back_refresh_button_icon()

        self.spinner1.stop()
        self.timeout_id = 0
        return False

    def on_valid_fingerprint(self, app, key):
        self.log.info("Signal emitted: valid-fingerprint: {}".format(key.fingerprint))
        download_time = 3
        self.timeout_id = GLib.timeout_add_seconds(download_time, self.download_key, key, priority=GLib.PRIORITY_DEFAULT)

    def sign_key(self, key, uidslist):
        self.succes_fail_signing_label.set_markup("Key succesfully signed!")
        self.succes_fail_signing_label.show()

        self.spinner2.stop()
        self.timeout_id = 0
        return False

    def on_sign_key_confirmed(self, app, key, uidslist):
        self.log.info("Signal emitted: sign-key-confirmed: {}".format(key))

        uids_repr = format_uidslist(uidslist)
        uids_signed_label = self.builder.get_object("uids_signed_label")
        uids_signed_label.set_markup(uids_repr)

        signing_time = 2
        self.timeout_id = GLib.timeout_add_seconds(signing_time, self.sign_key, key, uidslist, priority=GLib.PRIORITY_DEFAULT)

    def get_app_state(self):
        return self.state

    def update_app_state(self, new_state=None):
        self.last_state = self.state

        if self.last_state == DOWNLOAD_KEY_STATE:
            # Reset download timer
            if self.timeout_id != 0:
                GLib.source_remove(self.timeout_id)
                self.timeout_id = 0

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
        cleaned_fpr = clean_fingerprint(entryObject.get_text())
        self.log.debug("Gtk.Entry text changed: {}".format(cleaned_fpr))

        if is_valid_fingerprint(cleaned_fpr):
            keys = gpgmh.get_usable_secret_keys()
            for key in keys:

                if key.fingerprint == cleaned_fpr:
                    keyIdsLabel = self.builder.get_object("key_ids_label")
                    keyIdsLabel.set_markup(format_key_header(key.fingerprint))

                    uidsLabel = self.builder.get_object("uids_label")
                    markup = format_uidslist(key.uidslist)
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
        key = listBoxRowObject.key

        keyidLabel = self.builder.get_object("keyidLabel")
        key_header = format_key_header(key.fingerprint)
        keyidLabel.set_markup(key_header)

        uidsLabel = self.builder.get_object("uidsLabel")
        uidsLabel.set_markup(format_uidslist(key.uidslist))

        fpr = format_fingerprint(key.fingerprint)
        keyFingerprintLabel = self.builder.get_object("keyFingerprintLabel")
        keyFingerprintLabel.set_markup('<span size="20000">' + fpr + '</span>')
        keyFingerprintLabel.set_selectable(True)


        qr_frame = self.builder.get_object("qrcode_frame")
        for child in qr_frame.get_children():
            if type(child) == QRCodeWidget:
                qr_frame.remove(child)

        qr_data = key.fingerprint[-8:]
        qr_frame.add(QRCodeWidget(qr_data))
        qr_frame.show_all()

        self.stack2.set_visible_child_name('page1')
        self.update_app_state(PRESENT_KEY_STATE)
        self.update_back_refresh_button_icon()

    def on_row_selected(self, listBoxObject, listBoxRowObject, builder, *args):
        self.log.debug("ListRow selected!Key '{}'' selected".format(listBoxRowObject.key))

    def on_cancel_download_button_clicked(self, buttonObject, *args):
        self.log.debug("Cancel download button clicked.")
        if self.timeout_id != 0:
            GLib.source_remove(self.timeout_id)
            self.error_download_label.show()
            self.timeout_id = 0

        self.spinner1.stop()

    def on_confirm_button_clicked(self, buttonObject, *args):
        self.log.debug("Confirm sign button clicked.")

        self.succes_fail_signing_label.hide()
        self.spinner2.start()

        self.stack3.set_visible_child_name('page3')
        self.update_app_state(SIGN_KEY_STATE)
        self.update_back_refresh_button_icon()

        # FIXME user should be able to choose which UIDs he wants to sign
        uids_to_sign = self.key.uidslist
        self.emit('sign-key-confirmed', self.key, uids_to_sign)

    def on_cancel_signing_button_clicked(self, buttonObject, *args):
        self.log.debug("Cancel signing button clicked.")
        if self.timeout_id != 0:
            GLib.source_remove(self.timeout_id)
            self.succes_fail_signing_label.set_markup('Key signing was interrupted!')
            self.succes_fail_signing_label.show()
            self.timeout_id = 0

        self.spinner2.stop()

    def on_redo_button_clicked(self, buttonObject, *args):
        self.log.debug("Redo button clicked.")
        pass

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
