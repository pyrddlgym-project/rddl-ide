'''A modern popup menu, used by the menu bar and by the choosers of the policy form in
place of Tk's native menu (which Windows draws in its classic style).'''
import ctypes
import sys
import tkinter
from tkinter import font as tkfont
from typing import Callable, List, Optional, Tuple, Union

from customtkinter import CTkFont, CTkOptionMenu, ThemeManager, get_appearance_mode

SEPARATOR = None
Item = Union[Tuple[str, Callable[[], None]], None]

# sizes before DPI scaling
ROW_HEIGHT = 28
PADDING = 4
SEPARATOR_HEIGHT = 9
TEXT_INSET = 12
CHECK_WIDTH = 22
RIGHT_INSET = 28
FONT_SIZE = 14
SCROLLBAR_WIDTH = 6
SCREEN_MARGIN = 8
TYPEAHEAD_PAUSE = 1000


def palette(name: str) -> str:
    '''A color of the app's palette (theme.json) for the current appearance.'''
    (light, dark) = ThemeManager.theme['Palette'][name]
    return dark if get_appearance_mode() == 'Dark' else light


def _rounded_rectangle(canvas, x1, y1, x2, y2, radius, **kwargs):
    r = radius
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
              x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def work_area(widget: tkinter.Misc, x: int, y: int) -> Tuple[int, int, int, int]:
    '''The (left, top, right, bottom) of the screen at (x, y), less the taskbar, in the
    pixels of winfo_rootx.'''
    if sys.platform.startswith('win'):
        try:
            from ctypes import wintypes

            class MonitorInfo(ctypes.Structure):
                _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                            ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]

            user32 = ctypes.windll.user32
            monitor = user32.MonitorFromPoint(wintypes.POINT(x, y), 2)
            info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = info.rcWork
                return (work.left, work.top, work.right, work.bottom)
        except Exception:
            pass
    return (0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight())


class PopupMenu:
    '''Shows items (label, command) and SEPARATORs below the anchor widget until one is
    chosen, a click lands outside, Escape is pressed or the window moves.'''

    def __init__(self, anchor: tkinter.Misc, items: List[Item], 
                 selected: Optional[str]=None,
                 min_width: int=0, on_close: Optional[Callable[[], None]]=None,
                 on_pointer: Optional[Callable[[int, int], bool]]=None):
        self.anchor = anchor
        self.items = items
        self.on_close = on_close
        self.on_pointer = on_pointer
        self.closed = False
        scale = anchor._get_widget_scaling() if hasattr(anchor, '_get_widget_scaling') \
            else 1.0
        s = lambda value: max(1, round(value * scale))
        self.row_height = s(ROW_HEIGHT)

        self.font = tkfont.Font(family=CTkFont().cget('family'), size=-s(FONT_SIZE))
        checkable = selected is not None
        text_x = s(CHECK_WIDTH + TEXT_INSET) if checkable else s(TEXT_INSET)

        # the rows: (top, bottom, item index) of each choosable item
        (pad, y) = (s(PADDING), s(PADDING))
        self.rows, separators = [], []
        for (i, item) in enumerate(items):
            if item is SEPARATOR:
                separators.append(y + s(SEPARATOR_HEIGHT) // 2)
                y += s(SEPARATOR_HEIGHT)
            else:
                self.rows.append((y, y + s(ROW_HEIGHT), i))
                y += s(ROW_HEIGHT)
        total = y + pad

        # the height
        (x, below, above) = (
            anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height(),
            anchor.winfo_rooty()
        )
        (left, top, right, bottom) = work_area(anchor, x, above)
        (gap, margin) = (s(2), s(SCREEN_MARGIN))
        room = bottom - top - 2 * margin - 2
        if room < total <= room + pad:
            total = room
        height = min(total, room)
        self.scrollable = total > height
        self.scrollbar_width = s(SCROLLBAR_WIDTH) if self.scrollable else 0

        labels = [item[0] for item in items if item is not SEPARATOR]
        width = max([min_width, s(160)] + [
            text_x + self.font.measure(label) + s(RIGHT_INSET)
            for label in labels
        ]) + self.scrollbar_width

        # the place: below the anchor, else above it, else wherever it fits on the screen
        if below + gap + height + 2 <= bottom - margin:
            y_window = below + gap
        elif above - gap - height - 2 >= top + margin:
            y_window = above - gap - height - 2
        else:
            y_window = max(top + margin, bottom - margin - height - 2)
        x = max(left, min(x, right - width - 2))

        # the window: a 1px border around the canvas
        self.window = window = tkinter.Toplevel(anchor)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes('-topmost', True)
        window.configure(bg=palette('popup_border'))
        window.geometry(f'{width + 2}x{height + 2}+{x}+{y_window}')
        self.canvas = canvas = tkinter.Canvas(
            window, width=width, height=height, bg=palette('popup'), highlightthickness=0,
            bd=0, yscrollincrement=1, scrollregion=(0, 0, width, total))
        canvas.place(x=1, y=1, width=width, height=height)

        # draw: a hidden highlight per row, then the texts and check mark above it
        self.highlights = {}
        row_right = width - pad - self.scrollbar_width
        for (row_top, row_bottom, i) in self.rows:
            self.highlights[i] = _rounded_rectangle(
                canvas, pad, row_top + 1, row_right, row_bottom - 1, s(4), 
                fill='', outline='')
            middle = (row_top + row_bottom) // 2
            canvas.create_text(text_x, middle, anchor='w', text=items[i][0],
                               font=self.font, fill=palette('text'))
            if checkable and items[i][0] == selected:
                canvas.create_text(s(TEXT_INSET), middle, anchor='w', text='✓',
                                   font=self.font, fill=palette('accent'))
        for middle in separators:
            canvas.create_line(
                s(10), middle, width - s(10), middle, fill=palette('border'))
        self.thumb = canvas.create_rectangle(0, 0, 0, 0, fill='', outline='')
        self.dragging = None
        self.pressed = False
        self.typed, self.typed_at = '', 0

        # pointer events are handled from screen coordinates at the window
        self.hovered = None
        window.bind('<Motion>', self._motion)
        window.bind('<ButtonPress>', self._press)
        window.bind('<ButtonRelease-1>', self._release)
        window.bind('<MouseWheel>', self._wheel)
        window.bind('<Escape>', lambda _: self.close())
        window.bind('<Up>', lambda _: self._step(-1))
        window.bind('<Down>', lambda _: self._step(1))
        window.bind('<Prior>', lambda _: self._page(-1))
        window.bind('<Next>', lambda _: self._page(1))
        window.bind('<Return>', lambda _: self._choose(self.hovered))
        window.bind('<KeyPress>', self._typeahead)
        window.bind('<FocusOut>', self._keep_focus)
        self._origin = self._window_position()
        window.after(100, self._close_if_window_moved)

        window.deiconify()
        window.lift()
        window.focus_force()
        self._grab()
        if selected is not None:
            self._reveal(
                next((i for (_, _, i) in self.rows if items[i][0] == selected), None))
        self._draw_thumb()

    # ===========================================================================
    # events
    # ===========================================================================

    def _row_at(self, x_root, y_root) -> Optional[int]:
        if not self._inside(x_root, y_root) or self._on_scrollbar(x_root):
            return None
        y_canvas = self.canvas.canvasy(y_root - self.canvas.winfo_rooty())
        return next(
            (i for (top, bottom, i) in self.rows if top <= y_canvas < bottom), None)

    def _on_scrollbar(self, x_root) -> bool:
        x = x_root - self.canvas.winfo_rootx()
        return self.scrollable \
            and x >= int(self.canvas.cget('width')) - self.scrollbar_width - 2

    def _highlight(self, index) -> None:
        if index == self.hovered:
            return
        if self.hovered is not None:
            self.canvas.itemconfigure(self.highlights[self.hovered], fill='')
        if index is not None:
            self.canvas.itemconfigure(self.highlights[index], fill=palette('hover'))
        self.hovered = index

    def _inside(self, x_root, y_root) -> bool:
        w = self.window
        return (
            w.winfo_rootx() <= x_root < w.winfo_rootx() + w.winfo_width() and \
            w.winfo_rooty() <= y_root < w.winfo_rooty() + w.winfo_height()
        )

    def _motion(self, event) -> None:
        if self.dragging is not None:
            (y_start, first_start) = self.dragging
            track = int(self.canvas.cget('height')) - 6
            self.canvas.yview_moveto(first_start + (event.y_root - y_start) / track)
            self._draw_thumb()
            return
        self._highlight(self._row_at(event.x_root, event.y_root))
        if not self._inside(event.x_root, event.y_root) and self.on_pointer is not None:
            self.on_pointer(event.x_root, event.y_root)

    def _press(self, event) -> None:
        if not self._inside(event.x_root, event.y_root):
            self.close()
        elif event.num in (4, 5):
            self._scroll(3 * self.row_height * (-1 if event.num == 4 else 1))
        elif event.num == 1:
            self.pressed = True
            if self._on_scrollbar(event.x_root):
                (first, last) = self.canvas.yview()
                track = int(self.canvas.cget('height')) - 6
                y = event.y_root - self.canvas.winfo_rooty() - 3
                if not first * track <= y <= last * track:
                    self.canvas.yview_moveto(y / track - (last - first) / 2)
                    self._draw_thumb()
                self.dragging = (event.y_root, self.canvas.yview()[0])

    def _release(self, event) -> None:
        (pressed, self.pressed) = (self.pressed, False)
        if self.dragging is not None:
            self.dragging = None
        elif pressed:
            self._choose(self._row_at(event.x_root, event.y_root))

    def _wheel(self, event) -> None:
        if sys.platform == 'darwin':
            self._scroll(-event.delta * self.row_height // 2)
        else:
            self._scroll(-round(event.delta / 120 * 3 * self.row_height))

    def _scroll(self, pixels) -> None:
        if self.scrollable and pixels:
            self.canvas.yview_scroll(pixels, 'units')
            self._draw_thumb()

    def _step(self, direction, count=1) -> None:
        indices = [i for (_, _, i) in self.rows]
        if not indices:
            return
        if self.hovered is None:
            index = indices[0] if direction > 0 else indices[-1]
        else:
            position = indices.index(self.hovered) + direction * count
            index = indices[max(0, min(position, len(indices) - 1))]
        self._highlight(index)
        self._reveal(index)

    def _page(self, direction) -> None:
        visible = max(1, int(self.canvas.cget('height')) // self.row_height - 1)
        self._step(direction, visible)

    def _typeahead(self, event) -> None:
        '''Typing jumps to the first item that starts with what was typed.'''
        if not event.char or not event.char.isprintable() or event.char.isspace():
            return
        if event.time - self.typed_at > TYPEAHEAD_PAUSE:
            self.typed = ''
        (self.typed, self.typed_at) = (self.typed + event.char.lower(), event.time)
        match = next((i for (_, _, i) in self.rows
                      if self.items[i][0].lower().startswith(self.typed)), None)
        if match is not None:
            self._highlight(match)
            self._reveal(match)

    def _reveal(self, index) -> None:
        '''Scrolls the row of the item into view.'''
        if index is None or not self.scrollable:
            return
        (top, bottom, _) = next(row for row in self.rows if row[2] == index)
        view_top = self.canvas.canvasy(0)
        view_bottom = view_top + int(self.canvas.cget('height'))
        if top < view_top:
            self.canvas.yview_scroll(top - int(view_top) - self.row_height, 'units')
        elif bottom > view_bottom:
            self.canvas.yview_scroll(bottom - int(view_bottom) + self.row_height, 'units')
        self._draw_thumb()

    def _draw_thumb(self) -> None:
        '''The scrollbar's thumb, when the list scrolls.'''
        if not self.scrollable:
            return
        (first, last) = self.canvas.yview()
        top = self.canvas.canvasy(0)
        track = int(self.canvas.cget('height')) - 6
        right = int(self.canvas.cget('width')) - 3
        self.canvas.delete(self.thumb)
        self.thumb = _rounded_rectangle(
            self.canvas, right - self.scrollbar_width, top + 3 + first * track,
            right, top + 3 + last * track, self.scrollbar_width // 2, outline='',
            fill=palette('scrollbar'))

    def _grab(self, attempts: int=50) -> None:
        '''Grabs the pointer, so that clicks outside the popup reach it (and close it).'''
        if self.closed:
            return
        try:
            self.window.grab_set()
        except tkinter.TclError:
            if attempts > 0:
                self.window.after(10, lambda: self._grab(attempts - 1))

    def _keep_focus(self, _) -> None:
        '''Takes the focus back when another widget of the app gets it.'''
        def refocus():
            if self.closed:
                return
            try:
                focus = self.window.focus_get()
            except KeyError:
                return
            if focus is not None and focus.winfo_toplevel() is not self.window:
                self.window.focus_force()
        self.window.after(1, refocus)

    def _window_position(self):
        toplevel = self.anchor.winfo_toplevel()
        return (toplevel.winfo_rootx(), toplevel.winfo_rooty())

    def _close_if_window_moved(self) -> None:
        '''The popup does not follow the app window, so it closes when that moves.'''
        if self.closed:
            return
        try:
            if self._window_position() != self._origin:
                self.close()
            else:
                self.window.after(100, self._close_if_window_moved)
        except tkinter.TclError:
            self.close()

    def _choose(self, index) -> None:
        if index is None:
            return
        command = self.items[index][1]
        self.close()
        command()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.window.grab_release()
            self.window.destroy()
        except tkinter.TclError:
            pass
        if self.on_close is not None:
            self.on_close()


class ChoiceMenu(CTkOptionMenu):
    '''A CTkOptionMenu whose list opens as a PopupMenu.'''

    def _open_dropdown_menu(self):
        self.popup = PopupMenu(
            self, [(value, lambda value=value: self._dropdown_callback(value))
                   for value in self._values],
            selected=self._current_value, min_width=self.winfo_width())


class MenuBarMenu:
    '''A menu of a CTkMenuBar, opened by its button.'''

    _menus: List['MenuBarMenu'] = []

    def __init__(self, widget):
        self.button = widget
        self.items: List[Item] = []
        self.popup: Optional[PopupMenu] = None
        widget.configure(command=self.open, corner_radius=4, fg_color='transparent',
                         hover_color=ThemeManager.theme['Palette']['hover'],
                         text_color=ThemeManager.theme['Palette']['text'])
        MenuBarMenu._menus.append(self)

    def add_option(self, option: str, command: Callable[[], None]) -> None:
        self.items.append((option, command))

    def add_separator(self) -> None:
        self.items.append(SEPARATOR)

    def open(self) -> None:
        for menu in MenuBarMenu._menus:
            if menu.popup is not None:
                menu.popup.close()
        self.button.configure(fg_color=ThemeManager.theme['Palette']['hover'])
        self.popup = PopupMenu(self.button, self.items, on_close=self._closed,
                               on_pointer=self._pointer)

    def _closed(self) -> None:
        self.popup = None
        try:
            self.button.configure(fg_color='transparent')
        except tkinter.TclError:
            pass

    def _pointer(self, x_root, y_root) -> bool:
        for menu in MenuBarMenu._menus:
            button = menu.button
            if (menu is not self and 
                button.winfo_toplevel() is self.button.winfo_toplevel() and
                button.winfo_rootx() <= x_root < button.winfo_rootx() + button.winfo_width() and
                button.winfo_rooty() <= y_root < button.winfo_rooty() + button.winfo_height()
            ):
                menu.open()
                return True
        return False
