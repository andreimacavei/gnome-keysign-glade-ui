#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import os
import logging
import signal
import sys
import time
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG, format='%(name)s (%(levelname)s): %(message)s')

from urlparse import urlparse, parse_qs

from .network.AvahiBrowser import AvahiBrowser
from .network import Keyserver

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from gi.repository import (
    GLib,
    GObject,
    Gio,
    Gtk,
    Gst
)

from datetime import date, datetime
from qrwidgets import QRCodeWidget, QRScannerWidget

try:
    import keysign.gpgmh as gpgmh
except ImportError as e:
    print e
    import gpgmh


Gst.init()


# The states that the app can have during run-time
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

def verify_downloaded_key(fpr, key):
    # FIXME: will be replaced with code that checks if the fingerprint
    # of the downloaded key is the same as the passed fpr
    return key if fpr == key.fingerprint else None

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

# FIXME: move this to a proper location
DATADIR = os.path.join(sys.prefix, "share", "keysign")

def ui_file(filename):
    return os.path.join(DATADIR, "ui", filename)


class ListBoxRowWithKey(Gtk.ListBoxRow):

    def __init__(self, key):
        super(ListBoxRowWithKey, self).__init__()
        self.key = key

        label = Gtk.Label()
        label.set_markup(format_listbox_key(self.key))
        self.add(label)


class Application(Gtk.Application):

    __gsignals__ = {
        'fingerprint-validated': (GObject.SIGNAL_RUN_LAST, None,
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

        self.log = logging.getLogger(__name__)
        self.builder = Gtk.Builder()
        try:
            self.builder.add_from_file(ui_file("applicationwindow.ui"))
            self.builder.add_from_file(ui_file("send.ui"))
            self.builder.add_from_file(ui_file("receive.ui"))
            self.builder.add_from_file(ui_file("menus.ui"))
            self.builder.add_from_file(ui_file("invalidkeydialog.ui"))
        except:
            self.log.exception("UI file not installed. Using current data dir.")
            # This might be the case when we want to test the app
            # without installing it.
            # It probably isn't the ideal way to do the switch
            try:
                self.builder.add_from_file("data/applicationwindow.ui")
                self.builder.add_from_file("data/send.ui")
                self.builder.add_from_file("data/receive.ui")
                self.builder.add_from_file("data/menus.ui")
                self.builder.add_from_file("data/invalidkeydialog.ui")
            except Exception as e:
                print e
                sys.exit()

        self.builder.connect_signals(self)
        self.window = None

        self.connect('fingerprint-validated', self.on_valid_fingerprint)
        self.connect('sign-key-confirmed', self.on_sign_key_confirmed)

        self.state = None
        self.last_state = None
        self.key = None
        self.timeout_id = 0

        self.keyserver = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        self.stack = self.builder.get_object('send_receive_stack')
        self.send_stack = self.builder.get_object('send_stack')
        self.receive_stack = self.builder.get_object('receive_stack')
        self.stack.add_titled(self.send_stack, 'send_stack', 'Send')
        self.stack.add_titled(self.receive_stack, 'receive_stack', 'Receive')
        self.stack.show_all()

        self.qrscanner = QRScannerWidget()
        scan_frame = self.builder.get_object("scan_frame")
        scan_frame.add(self.qrscanner)
        scan_frame.show_all()

        self.qrscanner.reader.connect('barcode', self.on_barcode)

        self.back_refresh_button = self.builder.get_object("back_refresh_button")
        self.error_download_label = self.builder.get_object("error_download_label")
        self.spinner1 = self.builder.get_object("spinner1")
        self.spinner2 = self.builder.get_object("spinner2")
        self.succes_fail_signing_label = self.builder.get_object("succes_fail_signing_label")
        # Update the key list with the user's own keys
        self.listbox = self.builder.get_object('keys_listbox')
        keys = gpgmh.get_usable_secret_keys()
        for key in keys:
            self.listbox.add(ListBoxRowWithKey(key))

        self.listbox.connect('row-activated', self.on_row_activated, self.builder)
        self.listbox.connect('row-selected', self.on_row_selected, self.builder)

        self.avahi_browser = None
        self.avahi_service_type = '_keysign._tcp'
        self.discovered_services = []
        GLib.idle_add(self.setup_avahi_browser)

        # Create menu action 'quit'
        action = Gio.SimpleAction.new('quit', None)
        action.connect('activate', lambda action, param: self.quit())
        self.add_action(action)

        # Create menu action 'about'
        action = Gio.SimpleAction.new('about', None)
        action.connect('activate', self.on_about)
        self.add_action(action)

        # Set up app menu
        self.set_app_menu(self.builder.get_object("app-menu"))

    def do_activate(self):
        # Set up the app window
        self.window = self.builder.get_object("applicationwindow1")

        self.add_window(self.window)
        self.window.show_all()

    def setup_avahi_browser(self):
        self.avahi_browser = AvahiBrowser(service=self.avahi_service_type)
        self.avahi_browser.connect('new_service', self.on_new_service)
        self.avahi_browser.connect('remove_service', self.on_remove_service)

        return False

    def on_new_service(self, browser, name, address, port, txt_dict):
        published_fpr = txt_dict.get('fingerprint', None)

        self.log.info("Probably discovered something, let's check; %s %s:%i:%s",
                        name, address, port, published_fpr)

        if self.verify_service(name, address, port):
            GLib.idle_add(self.add_discovered_service, name, address, port, published_fpr)
        else:
            self.log.warn("Client was rejected: %s %s %i",
                        name, address, port)

    def on_remove_service(self, browser, service_type, name):
        '''Receives on_remove signal from avahibrowser.py to remove service from list and
        transfers data to remove_discovered_service'''
        self.log.info("Received a remove signal, let's check; %s:%s", service_type, name)
        GLib.idle_add(self.remove_discovered_service, name)

    def verify_service(self, name, address, port):
        '''A tiny function to return whether the service
        is indeed something we are interested in'''
        return True

    def add_discovered_service(self, name, address, port, published_fpr):
        self.discovered_services += ((name, address, port, published_fpr), )
        #List needs to be modified when server services are removed.
        self.log.info("Clients currently in list '%s'", self.discovered_services)
        return False

    def remove_discovered_service(self, name):
        '''Removes server-side clients from discovered_services list
        when the server name with fpr is a match.'''
        for client in self.discovered_services:
            if client[0] == name:
                self.discovered_services.remove(client)
        self.log.info("Clients currently in list '%s'", self.discovered_services)


    def update_key_list(self):
        #FIXME do not remove rows, but update data
        for listrow in self.listbox:
            self.listbox.remove(listrow)

        keys = gpgmh.get_usable_secret_keys()
        for key in keys:
            self.listbox.add(ListBoxRowWithKey(key))
        self.listbox.show_all()

    def sign_key(self, key, uids):
        self.succes_fail_signing_label.set_markup("Key succesfully signed!")
        self.succes_fail_signing_label.show()

        self.spinner2.stop()
        self.timeout_id = 0
        return False

    def on_sign_key_confirmed(self, app, key, uidslist):
        self.log.info("Signal emitted: sign-key-confirmed: \n{}".format(key))

        uids_repr = format_uidslist(uidslist)
        uids_signed_label = self.builder.get_object("uids_signed_label")
        uids_signed_label.set_markup(uids_repr)

        signing_time = 2
        self.timeout_id = GLib.timeout_add_seconds(signing_time,
                                                   self.sign_key, key,
                                                   uidslist,
                                                   priority=GLib.PRIORITY_DEFAULT)

    def get_app_state(self):
        return self.state

    def update_app_state(self, new_state=None):
        self.last_state = self.state

        if self.last_state == DOWNLOAD_KEY_STATE:
            # Reset download timer
            if self.timeout_id != 0:
                GLib.source_remove(self.timeout_id)
                self.timeout_id = 0
        elif self.last_state == PRESENT_KEY_STATE:
            # Shutdown key server
            if self.keyserver:
                self.log.debug("Keyserver switched off")
                self.stop_server()

        if new_state:
            self.state = new_state
        else:
            visible_top_child = self.stack.get_visible_child()
            if visible_top_child == self.send_stack:
                page = self.send_stack.get_visible_child_name()
                self.state = SELECT_KEY_STATE if page == 'page0' else PRESENT_KEY_STATE
            elif visible_top_child == self.receive_stack:
                page = self.receive_stack.get_visible_child_name()
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
            self.send_stack.set_visible_child_name('page0')
            self.update_app_state(SELECT_KEY_STATE)
        elif state == ENTER_FPR_STATE:
            self.update_app_state(ENTER_FPR_STATE)
        elif state == DOWNLOAD_KEY_STATE:
            self.receive_stack.set_visible_child_name('page0')
            self.update_app_state(ENTER_FPR_STATE)
        elif state == CONFIRM_KEY_STATE:
            self.receive_stack.set_visible_child_name('page0')
            self.update_app_state(ENTER_FPR_STATE)
        elif state == SIGN_KEY_STATE:
            self.receive_stack.set_visible_child_name('page2')
            self.update_app_state(CONFIRM_KEY_STATE)
        else:
            self.log.error("Unknown application state!")

        self.update_back_refresh_button_icon()


    def download_keys(self, fpr=None):
        # FIXME: this will be replaced with code that downloads
        # data from network
        if not fpr:
            return gpgmh.get_usable_secret_keys()
        else:
            res = []
            keys = gpgmh.get_usable_secret_keys()
            for key in keys:
                if key.fingerprint == fpr:
                    res.append(key)
        return res

    def obtain_key_async(self, cleaned_fpr, callback, error_cb):
        self.log.debug("Obtaining key with fpr: {}".format(cleaned_fpr))

        # ToBeNoted(TBN): An attacker can publish a network service with the
        # same fingerprint in it's TXT record as another participant. This is
        # why we download all data from the network and verify it afterwards.
        keys = self.download_keys(cleaned_fpr)
        key = None

        for keydata in keys:
            key = verify_downloaded_key(cleaned_fpr, keydata)
            if key:
                break

        if key:
            self.key = key
            GLib.idle_add(callback, key)
        else:
            GLib.idle_add(error_cb)

        return False

    def on_valid_fingerprint(self, app, cleaned_fpr):
        self.error_download_label.hide()
        self.spinner1.start()

        self.receive_stack.set_visible_child_name('page1')
        self.update_app_state(DOWNLOAD_KEY_STATE)
        self.update_back_refresh_button_icon()

        # GLib.idle_add(self.obtain_key_async, cleaned_fpr)
        download_time = 3
        self.timeout_id = GLib.timeout_add_seconds(download_time,
                                                    self.obtain_key_async,
                                                    cleaned_fpr,
                                                    self.received_key_callback,
                                                    self.invalid_key_callback,
                                                    priority=GLib.PRIORITY_DEFAULT)

    def received_key_callback(self, key):
        self.log.debug("Called received_key_callback")

        self.spinner1.stop()
        keyIdsLabel = self.builder.get_object("key_ids_label")
        keyIdsLabel.set_markup(format_key_header(key.fingerprint))

        uidsLabel = self.builder.get_object("uids_label")
        markup = format_uidslist(key.uidslist)
        uidsLabel.set_markup(markup)

        self.timeout_id = 0
        self.receive_stack.set_visible_child_name('page2')
        self.update_app_state(CONFIRM_KEY_STATE)
        self.update_back_refresh_button_icon()

    def invalid_key_callback(self):
        self.log.debug("Called invalid_key_callback")

        dialog = self.builder.get_object('invalid_dialog')
        dialog.set_transient_for(self.window)

        response = dialog.run()
        if response == Gtk.ResponseType.CLOSE:
            self.log.debug("WARN dialog closed by clicking CLOSE button")
            pass
        dialog.destroy()

        self.receive_stack.set_visible_child_name('page0')
        self.update_app_state(ENTER_FPR_STATE)
        self.update_back_refresh_button_icon()

    def on_text_changed(self, entryObject, *args):
        cleaned_fpr = clean_fingerprint(entryObject.get_text())

        if is_valid_fingerprint(cleaned_fpr):

            self.emit('fingerprint-validated', cleaned_fpr)

    def parse_barcode(self, barcode_string):
        """Parses information contained in a barcode

        It returns a dict with the parsed attributes.
        We expect the dict to contain at least a 'fingerprint'
        entry. Others might be added in the future.
        """
        # The string, currently, is of the form
        # openpgp4fpr:foobar?baz=qux#frag=val
        # Which urlparse handles perfectly fine.
        p = urlparse(barcode_string)
        self.log.debug("Parsed %r into %r", barcode_string, p)
        fpr = p.path
        query = parse_qs(p.query)
        fragments = parse_qs(p.fragment)
        rest = {}
        rest.update(query)
        rest.update(fragments)
        # We should probably ensure that we have only one
        # item for each parameter and flatten them accordingly.
        rest['fingerprint'] = fpr

        self.log.debug('Parsed barcode into %r', rest)
        return rest

    def on_barcode(self, sender, barcode, message, image):
        '''This is connected to the "barcode" signal.

        The function will advance the application if a reasonable
        barcode has been provided.

        Sender is the emitter of the signal and should be the scanning
        widget.

        Barcode is the actual barcode that got decoded.

        The message argument is a GStreamer message that created
        the barcode.

        When image is set, it should be the frame as pixbuf that
        caused a barcode to be decoded.
        '''
        self.log.info("Barcode signal %r %r", barcode, message)
        parsed = self.parse_barcode(barcode)
        fingerprint = parsed['fingerprint']
        if not fingerprint:
            self.log.error("Expected fingerprint in %r to evaluate to True, "
                           "but is %r", parsed, fingerprint)
        else:
            if is_valid_fingerprint(fingerprint):
                self.emit('fingerprint-validated', fingerprint)

    def on_row_activated(self, listBoxObject, listBoxRowObject, builder, *args):
        key = listBoxRowObject.key

        keyidLabel = self.builder.get_object("keyidLabel")
        key_header = format_key_header(key.fingerprint)
        keyidLabel.set_markup(key_header)

        uidsLabel = self.builder.get_object("uidsLabel")
        uidsLabel.set_markup(format_uidslist(key.uidslist))

        fpr = format_fingerprint(key.fingerprint)
        keyFingerprintLabel = self.builder.get_object("keyFingerprintLabel")
        keyFingerprintLabel.set_markup(fpr)

        qr_frame = self.builder.get_object("qrcode_frame")
        for child in qr_frame.get_children():
            if type(child) == QRCodeWidget:
                qr_frame.remove(child)

        qr_data = 'OPENPGP4FPR:' + key.fingerprint
        qr_frame.add(QRCodeWidget(qr_data))
        qr_frame.show_all()

        self.log.debug("Keyserver switched on! Serving key with fpr: %s", fpr)
        # GLib.idle_add(self.setup_server(keydata, fpr))
        self.setup_server(key, key.fingerprint)

        self.send_stack.set_visible_child_name('page1')
        self.update_app_state(PRESENT_KEY_STATE)
        self.update_back_refresh_button_icon()

    def on_row_selected(self, listBoxObject, listBoxRowObject, builder, *args):
        self.log.debug("ListRow selected!Key:\n '{}'\n selected".format(listBoxRowObject.key))

    def setup_server(self, keydata, fingerprint):
        """
        Starts the key-server which serves the provided keydata and
        announces the fingerprint as TXT record using Avahi
        """
        self.log.info('Serving now')
        self.log.debug('About to call %r', Keyserver.ServeKeyThread)
        self.keyserver = Keyserver.ServeKeyThread(str(keydata), fingerprint)
        self.log.info('Starting thread %r', self.keyserver)
        self.keyserver.start()
        self.log.info('Finished serving')
        return False

    def stop_server(self):
        self.keyserver.shutdown()

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

        self.receive_stack.set_visible_child_name('page3')
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
