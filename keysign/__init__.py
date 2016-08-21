
__version__ = '0.1'



def main():
    # These imports were moved here because the keysign module
    # can be imported without wanting to run it, e.g. setup.py
    # imports the __version__

    import logging
    import signal
    import sys
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG, format='%(name)s (%(levelname)s): %(message)s')

    from gi.repository import GLib

    from .app import Application

    app = Application()

    try:
        GLib.unix_signal_add_full(GLib.PRIORITY_HIGH, signal.SIGINT, lambda *args : app.quit(), None)
    except AttributeError:
        pass

    exit_status = app.run(None)
    return exit_status
