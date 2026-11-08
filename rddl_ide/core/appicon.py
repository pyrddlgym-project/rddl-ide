'''Sets the app's icon on a window, on every platform.'''
import os
import sys
import tkinter

ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'icon.ico')


def set_icon(window: tkinter.Wm) -> None:
    '''Windows reads the .ico itself; elsewhere Tk takes iconbitmap names as X bitmaps
    (a .ico raises an error), so the icon is converted with Pillow when it is installed,
    and the window keeps the default icon otherwise.'''
    try:
        if sys.platform.startswith('win'):
            window.iconbitmap(ICON)
            return
        from PIL import Image, ImageTk
        window._app_icon = ImageTk.PhotoImage(Image.open(ICON), master=window)  # kept alive
        window.iconphoto(False, window._app_icon)
    except (ImportError, OSError, tkinter.TclError):
        pass
