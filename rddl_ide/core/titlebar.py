'''Colors the title bar of a window like the top of its content.'''
import sys
from tkinter import TclError

from customtkinter import AppearanceModeTracker, CTkToplevel, ThemeManager

DWMWA_USE_IMMERSIVE_DARK_MODE = (20, 19)  # the latter before Windows 10 20H1
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
RDW_INVALIDATE = 0x1
RDW_FRAME = 0x400
RETRY_MS = 25


def match_title_bar(window, background: str='chrome') -> None:
    '''Colors the title bar of a CTk window with the palette color background.'''
    if not sys.platform.startswith('win'):
        return
    if isinstance(window, CTkToplevel):
        window._deactivate_windows_window_header_manipulation = True

    def apply(*_):
        window.after_idle(set_when_shown)

    def set_when_shown(tries=40):
        '''Sets the colors once the window is shown again: they do not hold while Tk
        hides a transient window with its master.'''
        try:
            if window.state() == 'withdrawn' and tries > 0:
                window.after(RETRY_MS, lambda: set_when_shown(tries - 1))
            else:
                _set_colors(window, background)
        except TclError:
            pass

    apply()
    AppearanceModeTracker.add(apply, window)
    window.bind('<Destroy>', 
                lambda event: event.widget is window and
                    AppearanceModeTracker.remove(apply), add='+')


def _set_colors(window, background) -> None:
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        dark = ctypes.c_int(1 if window._get_appearance_mode() == 'dark' else 0)
        for attribute in DWMWA_USE_IMMERSIVE_DARK_MODE:
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(dark), ctypes.sizeof(dark)) == 0:
                break
        palette = ThemeManager.theme['Palette']
        for (attribute, name) in ((DWMWA_CAPTION_COLOR, background),
                                  (DWMWA_TEXT_COLOR, 'text'),
                                  (DWMWA_BORDER_COLOR, 'border')):
            value = ctypes.c_uint(_colorref(window._apply_appearance_mode(palette[name])))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
        ctypes.windll.user32.RedrawWindow(hwnd, None, None, RDW_FRAME | RDW_INVALIDATE)
    except Exception:
        pass


def _colorref(color: str) -> int:
    '''A Windows COLORREF (0x00BBGGRR) from '#RRGGBB'.'''
    (red, green, blue) = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return red | green << 8 | blue << 16
