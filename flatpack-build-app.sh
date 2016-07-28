#!/bin/bash

# Create the build directory
flatpak build-init keysign org.gnome.Keysign org.gnome.Sdk org.gnome.Platform 3.20

mkdir keysign/files/bin

flatpak build keysign cp *.ui /app/
flatpak build keysign cp gnome-keysign.py /app/bin
flatpak build keysign cp start-keysign.sh /app/bin

flatpak build-finish keysign --socket=x11 --command=start-keysign.sh

flatpak build-export repo keysign
flatpak --user remote-add --no-gpg-verify --if-not-exists keysign-repo repo
flatpak --user install keysign-repo org.gnome.Keysign
