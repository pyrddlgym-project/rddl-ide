'''Colors the title bar of a window like the top of its content.'''
import sys

from customtkinter import AppearanceModeTracker, ThemeManager

DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def match_title_bar(window, background: str='chrome') -> None:
    '''Colors the title bar of a CTk window with the palette color background.'''
    if not sys.platform.startswith('win'):
        return

    def apply(*_):
        window.after_idle(lambda: _set_colors(window, background))

    apply()
    AppearanceModeTracker.add(apply, window)
    window.bind('<Destroy>', 
                lambda event: event.widget is window and
                    AppearanceModeTracker.remove(apply), add='+')


def _set_colors(window, background) -> None:
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        palette = ThemeManager.theme['Palette']
        for (attribute, name) in ((DWMWA_CAPTION_COLOR, background),
                                  (DWMWA_TEXT_COLOR, 'text'),
                                  (DWMWA_BORDER_COLOR, 'border')):
            value = ctypes.c_uint(_colorref(window._apply_appearance_mode(palette[name])))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


def _colorref(color: str) -> int:
    '''A Windows COLORREF (0x00BBGGRR) from '#RRGGBB'.'''
    (red, green, blue) = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return red | green << 8 | blue << 16
