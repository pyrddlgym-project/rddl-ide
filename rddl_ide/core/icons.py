'''Toolbar icons, drawn with Pillow in the colors of the theme, and the icon buttons
that show them with a tooltip.

Each icon is drawn on a 24 x 24 grid with 2 units wide strokes, like common icon
sets, at a large size and then reduced, which smooths its edges. CTkImage scales it to
the screen and switches between the light and the dark versions with the theme.'''
import math
import tkinter
from functools import lru_cache
from tkinter import font

from customtkinter import CTkButton, CTkFont, CTkImage, ThemeManager
from PIL import Image, ImageChops, ImageDraw

from rddl_ide.core.popup import work_area

ICON_SIZE = 18  # on screen, before DPI scaling
BUTTON_SIZE = 28
GRID = 24  # the units of the drawings
DRAWN = 384  # pixels the drawings are made at
SOURCE = 96  # pixels the icons are reduced to, from which CTkImage scales them
STROKE = 1.75
TOOLTIP_FONT_SIZE = 13
TOOLTIP_DELAY = 600  # milliseconds the pointer rests on a button before its tooltip

RECORD_COLOR = ('#d13438', '#ff6b6b')


# ===========================================================================
# drawings: each draws in white on the mask of an icon, in grid units
# ===========================================================================

class _Pen:

    def __init__(self, mask):
        self.draw = ImageDraw.Draw(mask)
        self.unit = DRAWN / GRID

    def _xy(self, point):
        return (point[0] * self.unit, point[1] * self.unit)

    def _disc(self, center, radius, fill=255):
        (x, y), r = self._xy(center), radius * self.unit
        self.draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def line(self, *points, radius=0.0, closed=False, width=STROKE):
        '''A stroke through the points with round ends, its corners rounded with the
        radius.'''
        points = _rounded(points, radius, closed)
        if closed:
            points.append(points[0])
        self.draw.line([self._xy(p) for p in points], fill=255,
                       width=round(width * self.unit), joint='curve')
        for point in (points[0], points[-1]):
            self._disc(point, width / 2)

    def polygon(self, *points, radius=1.0):
        '''A filled polygon with rounded corners.'''
        points = _rounded(points, radius, closed=True)
        self.draw.polygon([self._xy(p) for p in points], fill=255)

    def circle(self, center, radius, fill=False, width=STROKE):
        self._disc(center, radius)
        if not fill:
            self._disc(center, radius - width, fill=0)

    def erase(self, *points):
        '''Clears a polygon, e.g. under a shape drawn over another.'''
        self.draw.polygon([self._xy(p) for p in points], fill=0)


def _rounded(points, radius, closed):
    '''The points of a path whose corners are replaced by curves of about the radius.'''
    points = [tuple(map(float, p)) for p in points]
    if radius <= 0:
        return points
    n = len(points)
    result = []
    for i in range(n):
        if not closed and i in (0, n - 1):
            result.append(points[i])
            continue
        (prev, corner, after) = (points[i - 1], points[i], points[(i + 1) % n])
        (a, b) = (math.dist(prev, corner), math.dist(corner, after))
        cut = min(radius, a / 2, b / 2)
        start = _towards(corner, prev, cut / a)
        end = _towards(corner, after, cut / b)
        for k in range(9):  # a quadratic Bezier curve with the corner as control
            t = k / 8
            result.append(tuple((1 - t) ** 2 * s + 2 * t * (1 - t) * c + t ** 2 * e
                                for (s, c, e) in zip(start, corner, end)))
    return result


def _towards(p, q, fraction):
    return (p[0] + (q[0] - p[0]) * fraction, p[1] + (q[1] - p[1]) * fraction)


def _new(pen):  # a page with a folded corner and a plus
    pen.line((14, 2.5), (5, 2.5), (5, 21.5), (19, 21.5), (19, 7.5), radius=2)
    pen.line((19, 7.5), (14, 2.5))
    pen.line((14, 2.5), (14, 7.5), (19, 7.5), radius=1)
    pen.line((12, 11.5), (12, 17.5))
    pen.line((9, 14.5), (15, 14.5))


def _load(pen):  # an open folder
    pen.line((5, 20), (2.5, 20), (2.5, 4), (9, 4), (11, 6.5), (18.5, 6.5), (18.5, 9.5),
             radius=1.5)
    pen.line((5, 20), (7, 10), (21.5, 10), (19.5, 20), closed=True, radius=1.5)


def _floppy(pen):
    pen.line((3, 3), (16, 3), (21, 8), (21, 21), (3, 21), closed=True, radius=2)
    pen.line((7.5, 3), (7.5, 7.5), (15, 7.5), radius=1)
    pen.line((7, 21), (7, 14.5), (17, 14.5), (17, 21), radius=1)


def _save(pen):
    _floppy(pen)


def _save_as(pen):  # the floppy with a pencil over its corner
    _floppy(pen)
    pen.erase((10.5, 24), (10.5, 19), (21, 8.5), (24, 8.5), (24, 24))
    pen.line((13.5, 21.5), (14, 18.5), (20.5, 12), (23, 14.5), (16.5, 21), closed=True,
             radius=0.5)


def _tray(pen):
    pen.line((3, 15), (3, 20.5), (21, 20.5), (21, 15), radius=1.5)


def _load_weights(pen):  # an arrow into a tray
    _tray(pen)
    pen.line((12, 3), (12, 15))
    pen.line((7.5, 10.5), (12, 15), (16.5, 10.5))


def _save_weights(pen):  # an arrow out of a tray
    _tray(pen)
    pen.line((12, 15), (12, 3))
    pen.line((7.5, 7.5), (12, 3), (16.5, 7.5))


def _run(pen):
    pen.polygon((7.5, 5), (18.5, 12), (7.5, 19), radius=1.5)


def _record(pen):
    pen.circle((12, 12), 6, fill=True)


def _stop(pen):
    pen.polygon((6.5, 6.5), (17.5, 6.5), (17.5, 17.5), (6.5, 17.5), radius=2)


def _moon(pen):  # the outline of a crescent: a disc with a disc taken out
    (center, radius) = ((11.5, 12.5), 9)
    (cut, cut_radius) = ((17, 7), 7)
    pen._disc(center, radius)
    pen._disc(cut, cut_radius, fill=0)
    inner = Image.new('L', pen.draw.im.size, 0)  # the crescent shrunk by the stroke
    shrunk = _Pen(inner)
    shrunk._disc(center, radius - STROKE)
    shrunk._disc(cut, cut_radius + STROKE, fill=0)
    pen.draw.bitmap((0, 0), inner, fill=0)


def _sun(pen):
    pen.circle((12, 12), 4.5)
    for k in range(8):
        angle = k * math.pi / 4
        (dx, dy) = (math.cos(angle), math.sin(angle))
        pen.line((12 + 7.5 * dx, 12 + 7.5 * dy), (12 + 9.5 * dx, 12 + 9.5 * dy))


DRAWINGS = {'new': _new, 'load': _load, 'save': _save, 'save_as': _save_as,
            'load_weights': _load_weights, 'save_weights': _save_weights, 'run': _run,
            'record': _record, 'stop': _stop, 'moon': _moon, 'sun': _sun}


@lru_cache(maxsize=None)
def _mask(name):
    mask = Image.new('L', (DRAWN, DRAWN), 0)
    DRAWINGS[name](_Pen(mask))
    return mask.resize((SOURCE, SOURCE), Image.LANCZOS)


def _colored(name, color):
    image = Image.new('RGBA', (SOURCE, SOURCE), color)
    image.putalpha(ImageChops.multiply(_mask(name), image.getchannel('A')))
    return image


def icon(name, colors=None, dark_name=None) -> CTkImage:
    '''The icon in the (light, dark) colors, by default those of the text; dark_name
    draws another icon in dark mode.'''
    (light, dark) = colors or ThemeManager.theme['Palette']['text']
    return CTkImage(light_image=_colored(name, light),
                    dark_image=_colored(dark_name or name, dark),
                    size=(ICON_SIZE, ICON_SIZE))


# ===========================================================================
# buttons
# ===========================================================================

class IconButton(CTkButton):
    '''A borderless button showing an icon, shaded on hover, with a tooltip.'''

    def __init__(self, master, name, tooltip, command, colors=None, dark_name=None,
                 **kwargs):
        palette = ThemeManager.theme['Palette']
        self._images = (icon(name, colors, dark_name),
                        icon(name, palette['text_muted'], dark_name))
        super().__init__(master, text='', image=self._images[0], command=command,
                         width=BUTTON_SIZE, height=BUTTON_SIZE, corner_radius=4,
                         fg_color='transparent', hover_color=palette['hover'],
                         border_spacing=0, **kwargs)
        Tooltip(self, tooltip)

    def set_enabled(self, enabled: bool) -> None:
        '''A disabled button shows its icon in the muted text color.'''
        try:
            self.configure(state='normal' if enabled else 'disabled',
                           image=self._images[0 if enabled else 1])
        except tkinter.TclError:  # the window was closed
            pass


class Tooltip:
    '''A label shown below a widget while the pointer rests on it.'''

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        self._pending = None
        # bound on the frame of the widget, which holds the parts the pointer moves over
        tkinter.Frame.bind(widget, '<Enter>', self._schedule, add='+')
        tkinter.Frame.bind(widget, '<Leave>', self._left, add='+')
        widget.bind('<ButtonPress>', lambda _: self._hide(), add=True)

    def _schedule(self, _=None):
        if self._pending is None and self.window is None:
            self._pending = self.widget.after(TOOLTIP_DELAY, self._show)

    def _inside(self):
        widget = self.widget
        (x, y) = widget.winfo_pointerxy()
        return (widget.winfo_rootx() <= x < widget.winfo_rootx() + widget.winfo_width() and
                widget.winfo_rooty() <= y < widget.winfo_rooty() + widget.winfo_height())

    def _left(self, _=None):
        try:
            if not self._inside():  # not just onto a part of the widget
                self._hide()
        except tkinter.TclError:
            pass

    def _show(self):
        self._pending = None
        try:
            if not self._inside():
                return
            palette = ThemeManager.theme['Palette']
            color = self.widget._apply_appearance_mode
            self.window = window = tkinter.Toplevel(self.widget)
            window.overrideredirect(True)
            window.attributes('-topmost', True)
            window.configure(bg=color(palette['popup_border']))
            scale = self.widget._get_widget_scaling()  # a Tk label is not scaled by CTk
            text_font = font.Font(family=CTkFont().cget('family'),
                                  size=-round(TOOLTIP_FONT_SIZE * scale))
            label = tkinter.Label(window, text=self.text, bg=color(palette['popup']),
                                  fg=color(palette['text']), font=text_font,
                                  padx=round(8 * scale), pady=round(3 * scale))
            label.pack(padx=1, pady=1)
            x = self.widget.winfo_rootx()
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + round(4 * scale)
            window.update_idletasks()
            right = work_area(self.widget, x, y)[2]
            x = max(0, min(x, right - window.winfo_reqwidth()))
            window.geometry(f'+{x}+{y}')
        except tkinter.TclError:
            self._hide()

    def _hide(self):
        if self._pending is not None:
            try:
                self.widget.after_cancel(self._pending)
            except tkinter.TclError:
                pass
            self._pending = None
        if self.window is not None:
            try:
                self.window.destroy()
            except tkinter.TclError:
                pass
            self.window = None
