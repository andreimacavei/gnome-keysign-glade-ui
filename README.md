#Gnome Keysign with new Builder UI

The goal of this project is to modernise [gnome-keysign](https://github.com/muelli/geysigning) project in terms of UI and codebase, as well as make it a flatpak app. The files needed for creating a flatpak app can be found [here](https://github.com/andreimacavei/gnome-keysign-flatpak).

## Tasks

- [x] Create the GUI components using GTK Builder and GLADE.
  - [x] Key Display Page: contains a listbox widget to display user's secret keys in a format
  - [x] Key Present Page: display information about a key with the help of some widgets.
    - [x] QR code widget: create the barcode widget that will be used to encode a key fingerprint
  - [x] Get Fingerprint Page: allows users to type a fpr or scan a barcode and decode the fingerprint.
    - [x] QR scanner widget: use video camera input to decode a barcode
  - [x] Key Sign Page: allows to sign a key obtained from the local network
  - [x] Create a custom HeaderBar widget for the app
  - [x] Create custom Menu

- [x] Create app states that makes it easier to know at each momment in what state the app is.
- [x] Create transition phases to give more feedback about the signing process
  - [x] Create downloading phase
  - [x] Create key signing phase

- [ ] Add functionality to the new UI
  - [x] GPG functionality
    - [x] Add a layer between gnome-keysign and the GPG library
  - [x] QR Code
  - [x] QR Scanner
  - [x] Avahi services
  - [x] Keyserver
  - [ ] Key download
  - [ ] Key signing

- [ ] App packaging and distribution

  - [x] Package the app using setuptools (install via `pip install`)
    - [x] Install source files
    - [x] Install glade files
    - [ ] Install desktop files
    - [ ] Install translation files

  - [x] Package the app using flatpak
    - [x] Create manifest file
    - [x] Create app bundle

## Building with `pip`

```sh
pip install --user .
```