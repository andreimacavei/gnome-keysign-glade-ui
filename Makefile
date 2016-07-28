

build-app:
	./flatpack-build-app.sh

run:
	flatpak run org.gnome.Keysign

clean:
	./flatpack-build-clean.sh
	rm *~ *.pyc