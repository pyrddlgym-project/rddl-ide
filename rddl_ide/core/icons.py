'''Toolbar icons, drawn with Pillow in the colors of the theme, and the icon buttons
that show them with a tooltip.'''
import math
import tkinter
from functools import lru_cache
from tkinter import font

from customtkinter import CTkButton, CTkFont, CTkImage, ThemeManager
from PIL import Image, ImageChops, ImageDraw

from rddl_ide.core.popup import work_area

ICON_SIZE = 18
BUTTON_SIZE = 28
GRID = 24  # the units of the drawings
DRAWN = 384  # pixels the drawings are made at
SOURCE = 96  # pixels the icons are reduced to, from which CTkImage scales them
STROKE = 1.75
TOOLTIP_FONT_SIZE = 13
TOOLTIP_DELAY = 600

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
        '''A stroke through the points with round ends, corners rounded with the radius.'''
        points = _rounded(points, radius, closed)
        if closed:
            points.append(points[0])
        self.draw.line([self._xy(p) for p in points], fill=255,
                       width=round(width * self.unit), joint='curve')
        for point in (points[0], points[-1]):
            self._disc(point, width / 2)

    def polygon(self, *points, radius=1.0):
        points = _rounded(points, radius, closed=True)
        self.draw.polygon([self._xy(p) for p in points], fill=255)

    def circle(self, center, radius, fill=False, width=STROKE):
        self._disc(center, radius)
        if not fill:
            self._disc(center, radius - width, fill=0)

    def erase(self, *points):
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
        for k in range(9):
            t = k / 8
            result.append(tuple((1 - t) ** 2 * s + 2 * t * (1 - t) * c + t ** 2 * e
                                for (s, c, e) in zip(start, corner, end)))
    return result


def _towards(p, q, fraction):
    return (p[0] + (q[0] - p[0]) * fraction, p[1] + (q[1] - p[1]) * fraction)


def _new(pen):
    pen.line((14, 2.5), (5, 2.5), (5, 21.5), (19, 21.5), (19, 7.5), radius=2)
    pen.line((19, 7.5), (14, 2.5))
    pen.line((14, 2.5), (14, 7.5), (19, 7.5), radius=1)
    pen.line((12, 11.5), (12, 17.5))
    pen.line((9, 14.5), (15, 14.5))


def _load(pen):
    pen.line((5, 20), (2.5, 20), (2.5, 4), (9, 4), (11, 6.5), (18.5, 6.5), (18.5, 9.5),
             radius=1.5)
    pen.line((5, 20), (7, 10), (21.5, 10), (19.5, 20), closed=True, radius=1.5)


def _floppy(pen):
    pen.line((3, 3), (16, 3), (21, 8), (21, 21), (3, 21), closed=True, radius=2)
    pen.line((7.5, 3), (7.5, 7.5), (15, 7.5), radius=1)
    pen.line((7, 21), (7, 14.5), (17, 14.5), (17, 21), radius=1)


def _save(pen):
    _floppy(pen)


def _save_as(pen):
    _floppy(pen)
    pen.erase((10.5, 24), (10.5, 19), (21, 8.5), (24, 8.5), (24, 24))
    pen.line((13.5, 21.5), (14, 18.5), (20.5, 12), (23, 14.5), (16.5, 21), closed=True,
             radius=0.5)


def _arc(center, radii, start, end, steps=24):
    '''Points of an elliptic arc, with angles in degrees (0 to the right, 90 down).'''
    return [(center[0] + radii[0] * math.cos(math.radians(a)),
             center[1] + radii[1] * math.sin(math.radians(a)))
            for a in (start + (end - start) * k / steps for k in range(steps + 1))]


def _repository(pen):
    '''A database: a cylinder of stacked disks.'''
    (left, right, rx, ry) = (4, 20, 8, 3)
    pen.line(*_arc((12, 5.5), (rx, ry), 0, 360, steps=48), closed=True)
    pen.line((left, 5.5), (left, 18.5))
    pen.line((right, 5.5), (right, 18.5))
    pen.line(*_arc((12, 12), (rx, ry), 0, 180))
    pen.line(*_arc((12, 18.5), (rx, ry), 0, 180))


def _tray(pen):
    pen.line((3, 15), (3, 20.5), (21, 20.5), (21, 15), radius=1.5)


def _load_weights(pen):
    _tray(pen)
    pen.line((12, 3), (12, 15))
    pen.line((7.5, 10.5), (12, 15), (16.5, 10.5))


def _save_weights(pen):
    _tray(pen)
    pen.line((12, 15), (12, 3))
    pen.line((7.5, 7.5), (12, 3), (16.5, 7.5))


def _run(pen):
    pen.polygon((7.5, 5), (18.5, 12), (7.5, 19), radius=1.5)


def _record(pen):
    pen.circle((12, 12), 6, fill=True)


def _stop(pen):
    pen.polygon((6.5, 6.5), (17.5, 6.5), (17.5, 17.5), (6.5, 17.5), radius=2)


def _undo(pen):
    pen.line((19.5, 19), (19.5, 8.5), (4.5, 8.5), radius=6)
    pen.line((8.5, 4.5), (4.5, 8.5), (8.5, 12.5))


def _redo(pen):
    pen.line((4.5, 19), (4.5, 8.5), (19.5, 8.5), radius=6)
    pen.line((15.5, 4.5), (19.5, 8.5), (15.5, 12.5))


def _cut(pen):
    pen.circle((6.5, 17.5), 3.5)
    pen.circle((17.5, 17.5), 3.5)
    pen.line((8.6, 14.6), (17, 2.5))
    pen.line((15.4, 14.6), (7, 2.5))


def _copy(pen):
    pen.line((4.5, 15.5), (2.5, 15.5), (2.5, 2.5), (15.5, 2.5), (15.5, 4.5), radius=2)
    pen.line((8.5, 8.5), (21.5, 8.5), (21.5, 21.5), (8.5, 21.5), closed=True, radius=2)


def _paste(pen):
    pen.line((8, 4.5), (4.5, 4.5), (4.5, 21.5), (19.5, 21.5), (19.5, 4.5), (16, 4.5),
             radius=2)
    pen.line((8.5, 2.5), (15.5, 2.5), (15.5, 6.5), (8.5, 6.5), closed=True, radius=1)


def _wrap(pen):
    pen.line((3.5, 5.5), (20.5, 5.5))
    pen.line((3.5, 12), (17, 12), (20.5, 12), (20.5, 18.5), (13, 18.5), radius=3.25)
    pen.line((15.5, 16), (13, 18.5), (15.5, 21))
    pen.line((3.5, 18.5), (8.5, 18.5))


def _find(pen):
    pen.circle((10.5, 10.5), 7)
    pen.line((15.5, 15.5), (20.5, 20.5))


def _replace(pen):
    pen.line((3, 3), (10, 3), (10, 10), (3, 10), closed=True, radius=1.5)
    pen.line((14, 14), (21, 14), (21, 21), (14, 21), closed=True, radius=1.5)
    pen.line((13.5, 6.5), (17.5, 6.5), (17.5, 10.5), radius=2)
    pen.line((15.5, 8.5), (17.5, 10.5), (19.5, 8.5))


def _goto(pen):
    for y in (5.5, 12, 18.5):
        pen.line((13, y), (21, y))
    pen.line((2.5, 12), (9, 12))
    pen.line((6, 9), (9, 12), (6, 15))


def _check(pen):
    pen.circle((12, 12), 9.5)
    pen.line((7.5, 12.5), (10.5, 15.5), (16.5, 9))


def _up(pen):
    pen.line((6.5, 14.5), (12, 9), (17.5, 14.5))


def _down(pen):
    pen.line((6.5, 9.5), (12, 15), (17.5, 9.5))


def _close(pen):
    pen.line((6.5, 6.5), (17.5, 17.5))
    pen.line((17.5, 6.5), (6.5, 17.5))


def _graph(pen):
    '''Two boxes joined into a third, as in a flow diagram.'''
    for (x, y) in ((2.5, 3), (2.5, 15.5), (15, 9.25)):
        pen.line((x, y), (x + 6.5, y), (x + 6.5, y + 5.5), (x, y + 5.5), closed=True,
                 radius=1.5)
    pen.line((9, 5.75), (12, 5.75), (12, 18.25), (9, 18.25), radius=1.5)
    pen.line((12, 12), (15, 12))


def _options(pen):
    '''Three sliders.'''
    for (y, knob) in ((5.5, 15), (12, 8), (18.5, 13)):
        pen.line((3, y), (knob - 2.75, y))
        pen.line((knob + 2.75, y), (21, y))
        pen.circle((knob, y), 2.75)


def _circular_arrow(pen, mirrored=False):
    '''An arrow going clockwise around a circle, or counterclockwise if mirrored.'''
    (center, radius, end) = ((12, 12.5), 7.5, 300)
    points = _arc(center, (radius, radius), 30, end)
    tip = points[-1]
    back = math.radians(end) - math.pi / 2  # against the direction of the arrow
    (left, right) = ((tip[0] + 4.5 * math.cos(back + turn),
                      tip[1] + 4.5 * math.sin(back + turn)) for turn in (0.8, -0.8))
    flip = (lambda p: (24 - p[0], p[1])) if mirrored else (lambda p: p)
    pen.line(*map(flip, points))
    pen.line(flip(left), flip(tip), flip(right))


def _refresh(pen):
    _circular_arrow(pen)


def _restart(pen):
    _circular_arrow(pen, mirrored=True)


def _step(pen):
    '''Step over: an arrow arching over a dot.'''
    points = _arc((12, 13), (7.5, 7), 180, 360)
    pen.line(*points)
    tip = points[-1]
    pen.line((tip[0] - 3.25, tip[1] - 3.25), tip, (tip[0] + 3.25, tip[1] - 3.25))
    pen.circle((12, 19.5), 2.25, fill=True)


def _run_to_end(pen):
    pen.polygon((4.5, 5), (15, 12), (4.5, 19), radius=1.5)
    pen.line((19, 5.5), (19, 18.5))


def _moon(pen):
    (center, radius) = ((11.5, 12.5), 9)
    (cut, cut_radius) = ((17, 7), 7)
    pen._disc(center, radius)
    pen._disc(cut, cut_radius, fill=0)
    inner = Image.new('L', pen.draw.im.size, 0)
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


DRAWINGS = {'new': _new, 'load': _load, 'repository': _repository, 'save': _save,
            'save_as': _save_as,
            'load_weights': _load_weights, 'save_weights': _save_weights, 'run': _run,
            'record': _record, 'stop': _stop, 'undo': _undo, 'redo': _redo, 'cut': _cut,
            'copy': _copy, 'paste': _paste, 'find': _find, 'replace': _replace,
            'goto': _goto, 'check': _check, 'up': _up, 'down': _down, 'close': _close,
            'wrap': _wrap, 'moon': _moon, 'sun': _sun, 'graph': _graph,
            'options': _options, 'refresh': _refresh, 'restart': _restart,
            'step': _step, 'run_to_end': _run_to_end}


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
    '''The icon in the (light, dark) colors.'''
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
        except tkinter.TclError:
            pass


class Tooltip:
    '''A label shown below a widget while the pointer rests on it.'''

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        self._pending = None
        tkinter.Frame.bind(widget, '<Enter>', self._schedule, add='+')
        tkinter.Frame.bind(widget, '<Leave>', self._left, add='+')
        widget.bind('<ButtonPress>', lambda _: self._hide(), add=True)

    def _schedule(self, _=None):
        if self._pending is None and self.window is None:
            self._pending = self.widget.after(TOOLTIP_DELAY, self._show)

    def _inside(self):
        widget = self.widget
        (x, y) = widget.winfo_pointerxy()
        return (
            widget.winfo_rootx() <= x < widget.winfo_rootx() + widget.winfo_width() and
            widget.winfo_rooty() <= y < widget.winfo_rooty() + widget.winfo_height()
        )

    def _left(self, _=None):
        try:
            if not self._inside():
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
            scale = self.widget._get_widget_scaling()
            text_font = font.Font(
                family=CTkFont().cget('family'), size=-round(TOOLTIP_FONT_SIZE * scale))
            label = tkinter.Label(
                window, 
                text=self.text, bg=color(palette['popup']), fg=color(palette['text']), 
                font=text_font, padx=round(8 * scale), pady=round(3 * scale))
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
