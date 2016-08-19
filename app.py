#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import signal
import sys
import time
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG, format='%(name)s (%(levelname)s): %(message)s')

from urlparse import urlparse, parse_qs

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

from qrwidgets import QRCodeWidget, QRScannerWidget

Gst.init()


_data = {
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
              'expiry':'2016-12-12',
              'nsigs':3
             },
    'key2' : {'id':'2048R/D32DFCFB 2015-08-20',
              'fpr':'B870D356F7ECD46CF2CEDF933BF372D3D32DFCFB',
              'uids':[
                    {'uid':'Foo Bar foo.bar@test.com',
                     'sigs':['D32DFCFB','6FB8DCCE']
                    }
                    ],
              'expiry':'2016-05-20',
              'nsigs':2
             },
    'key3' : {'id':'2048R/ED8312A2 2010-04-08',
              'fpr':'6011B4B032D3DED8312A2BEFDD433DCF8956D0D3',
              'uids':[
                    {'uid':'John Who john.who@test.com',
                     'sigs':['ED8312A2']
                    }
                    ],
              'expiry':'2016-07-14',
              'nsigs':1
             },
    'key4' : {'id':'2048R/D32DFCFB 2013-01-01',
              'fpr':'CEDF933BF372D3D32DFCFBB870D356F7ECD46CF2',
              'uids':[
                    {'uid':'Educated Foo edu.foo@test.com',
                     'sigs':['D32DFCFB','6FB8DCCE', '8956D0D3']
                    }
                    ],
              'expiry':'2020-05-05',
              'nsigs':3
             },
}

def get_secret_keys(pattern=None):
    data = None
    try:
        import keysign.gpgmh as gpgmh
    except ImportError as e:
        print e
        try:
            import gpgmh
        except ImportError as e:
            print e
            data = _data

    if data is None:
        keys = gpgmh.get_usable_secret_keys_dict()

        data = { k['fpr']: k   for k in keys['keys']}

    return _data

# The states that the app can have during run-time
UNKNOWN_STATE = 0
SELECT_KEY_STATE = 1
PRESENT_KEY_STATE = 2
ENTER_FPR_STATE = 3
DOWNLOAD_KEY_STATE = 4
CONFIRM_KEY_STATE = 5
SIGN_KEY_STATE = 6

def format_listbox_keydata(keydata):
    keyid = keydata['id']
    uids = keydata['uids']
    expire = keydata['expiry']
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


def verify_fingerprint(fpr, keys):
    for keyid,val in keys.items():
        key = keys[keyid]
        if val['fpr'] == fpr:
            return True
    return False

def verify_downloaded_key(fpr, key):
    # FIXME: will be replaced with code that checks if the fingerprint
    # of the downloaded key is the same as the passed fpr
    return key if fpr == key['fpr'] else None

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
        self.log = logging.getLogger(__name__)

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
        scan_frame.show_all()

        self.qrscanner.reader.connect('barcode', self.on_barcode)

        self.back_refresh_button = self.builder.get_object("button1")
        self.error_download_label = self.builder.get_object("error_download_label")
        self.spinner1 = self.builder.get_object("spinner1")
        self.spinner2 = self.builder.get_object("spinner2")
        self.succes_fail_signing_label = self.builder.get_object("succes_fail_signing_label")
        # Update the key list with the user's own keys
        self.listbox = self.builder.get_object('listbox1')
        keys = get_secret_keys()
        for keydata in keys.values():
            self.listbox.add(ListBoxRowWithKeyData(keydata))

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

        keys = get_secret_keys()
        for keydata in keys.values():
            self.listbox.add(ListBoxRowWithKeyData(keydata))
        self.listbox.show_all()

    def sign_key(self, key, uids):
        self.succes_fail_signing_label.set_markup("Key succesfully signed!")
        self.succes_fail_signing_label.show()

        self.spinner2.stop()
        self.timeout_id = 0
        return False

    def on_sign_key_confirmed(self, app, key, uids):
        self.log.info("Signal emitted: sign-key-confirmed: {}".format(key['id']))

        uids_repr = '\n'.join([uid['uid'] for uid in uids])
        uids_signed_label = self.builder.get_object("uids_signed_label")
        uids_signed_label.set_markup(uids_repr)

        signing_time = 2
        self.timeout_id = GLib.timeout_add_seconds(signing_time, self.sign_key, key, uids, priority=GLib.PRIORITY_DEFAULT)

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


    def download_keys(self, fpr=None):
        # FIXME: this will be replaced with code that downloads
        # data from network
        if not fpr:
            return _data.values()
        else:
            res = []
            for key,val in _data.items():
                if val['fpr'] == fpr:
                    res.append(val)
        return res

    def obtain_key_async(self, cleaned_fpr):
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
            self.spinner1.stop()
            self.timeout_id = 0

            keyIdsLabel = self.builder.get_object("key_ids_label")
            keyIdsLabel.set_markup(key['id'])

            uidsLabel = self.builder.get_object("uids_label")
            markup = ""
            for uid in key['uids']:
                markup += uid['uid'] + "\n"
            uidsLabel.set_markup(markup)

            self.stack3.set_visible_child_name('page2')
            self.update_app_state(CONFIRM_KEY_STATE)
            self.update_back_refresh_button_icon()
            self.key = key
        else:
            builder = Gtk.Builder.new_from_file("invalidkeydialog.ui")
            dialog = builder.get_object('invalid_dialog')
            dialog.set_transient_for(self.window)
            response = dialog.run()
            if response == Gtk.ResponseType.CLOSE:
                self.log.debug("WARN dialog closed by clicking CLOSE button")
                pass
            dialog.destroy()

            self.stack3.set_visible_child_name('page0')
            self.update_app_state(ENTER_FPR_STATE)
            self.update_back_refresh_button_icon()

        return False

    def on_valid_fingerprint(self, app, cleaned_fpr):
        self.error_download_label.hide()
        self.spinner1.start()

        # GLib.idle_add(self.obtain_key_async, cleaned_fpr)
        download_time = 3
        self.timeout_id = GLib.timeout_add_seconds(download_time,
                                                    self.obtain_key_async,
                                                    cleaned_fpr,
                                                    priority=GLib.PRIORITY_DEFAULT)

    def on_text_changed(self, entryObject, *args):
        cleaned_fpr = clean_fingerprint(entryObject.get_text())

        if is_valid_fingerprint(cleaned_fpr):
            self.stack3.set_visible_child_name('page1')
            self.update_app_state(DOWNLOAD_KEY_STATE)
            self.update_back_refresh_button_icon()

            self.emit('valid-fingerprint', cleaned_fpr)

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
                self.stack3.set_visible_child_name('page1')
                self.update_app_state(DOWNLOAD_KEY_STATE)
                self.update_back_refresh_button_icon()

                self.emit('valid-fingerprint', fingerprint)

    def on_row_activated(self, listBoxObject, listBoxRowObject, builder, *args):
        key = listBoxRowObject.data

        keyidLabel = self.builder.get_object("keyidLabel")
        keyid_str = "{0}".format(key['id'])
        keyidLabel.set_markup(keyid_str)

        uidsLabel = self.builder.get_object("uidsLabel")
        uidsLabel.set_markup(format_details_keydata(key))

        fpr = format_fpr(key['fpr'])
        keyFingerprintLabel = self.builder.get_object("keyFingerprintLabel")
        keyFingerprintLabel.set_markup('<span size="15000">' + fpr + '</span>')
        keyFingerprintLabel.set_selectable(True)


        qr_frame = self.builder.get_object("qrcode_frame")
        for child in qr_frame.get_children():
            if type(child) == QRCodeWidget:
                qr_frame.remove(child)

        qr_data = 'OPENPGP4FPR:' + key['fpr']
        qr_frame.add(QRCodeWidget(qr_data))
        qr_frame.show_all()

        self.stack2.set_visible_child_name('page1')
        self.update_app_state(PRESENT_KEY_STATE)
        self.update_back_refresh_button_icon()

    def on_row_selected(self, listBoxObject, listBoxRowObject, builder, *args):
        self.log.debug("ListRow selected!Key '{}'' selected".format(listBoxRowObject.data['id']))

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
        uids_to_sign = self.key['uids']
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
