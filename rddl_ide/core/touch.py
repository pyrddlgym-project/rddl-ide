'''Tablet mode: larger targets for a finger (buttons, fields, checkboxes, menu rows and
scrollbars) with text the same size, and editors that scroll when dragged. Widgets take
their touch sizes as they are shown and get their own sizes back when the mode is turned
off; what is drawn by hand reads size() and is drawn again by on_change().'''
import tkinter
from typing import Callable, Dict, List

from customtkinter import CTkButton, CTkCheckBox, CTkEntry, CTkOptionMenu, CTkScrollbar

TARGET = 40  # icon buttons, buttons and menu rows
FIELD = 36  # entries and choosers
ICON = 20
CHECKBOX = 26
SCROLLBAR = 20
SCROLLBAR_SPACING = 4

enabled = False
_redraws: List[Callable[[], None]] = []


def size(normal, touch):
    '''The size in the current mode.'''
    return touch if enabled else normal


def on_change(redraw: Callable[[], None]) -> None:
    '''Calls redraw() when the mode changes, until it raises TclError.'''
    _redraws.append(redraw)


def _touch_sizes(widget) -> Dict[str, int]:
    from rddl_ide.core.icons import IconButton
    if isinstance(widget, IconButton):
        return {'width': TARGET, 'height': TARGET}
    if isinstance(widget, CTkButton):
        return {'height': TARGET}
    if isinstance(widget, (CTkEntry, CTkOptionMenu)):
        return {'height': FIELD}
    if isinstance(widget, CTkCheckBox):
        return {'checkbox_width': CHECKBOX, 'checkbox_height': CHECKBOX}
    if isinstance(widget, CTkScrollbar):
        side = 'width' if widget.cget('orientation') == 'vertical' else 'height'
        return {side: SCROLLBAR, 'border_spacing': SCROLLBAR_SPACING}
    return {}


def _apply(widget) -> None:
    '''Gives the widget its touch sizes (never smaller than its own), or its own.'''
    sizes = _touch_sizes(widget)
    if not sizes or not (enabled or hasattr(widget, '_touch_normal')):
        return
    try:
        if not hasattr(widget, '_touch_normal'):
            widget._touch_normal = {key: widget.cget(key) for key in sizes}
        normal = widget._touch_normal
        widget.configure(**{key: max(normal[key], value) for (key, value) in sizes.items()}
                         if enabled else normal)
        from rddl_ide.core.icons import ICON_SIZE
        for image in getattr(widget, '_images', ()):
            image.configure(size=(size(ICON_SIZE, ICON),) * 2)
    except tkinter.TclError:
        pass


def _apply_all(widget) -> None:
    _apply(widget)
    for child in widget.winfo_children():
        _apply_all(child)


def install(root: tkinter.Misc) -> None:
    '''Gives the widgets of every window their touch sizes as they are shown.'''
    root.bind_all('<Map>', lambda event: enabled and _apply(event.widget), add='+')


def toggle(root: tkinter.Misc) -> None:
    '''Turns tablet mode on or off for every widget and what is drawn by hand.'''
    global enabled
    enabled = not enabled
    _apply_all(root)
    for redraw in list(_redraws):
        try:
            redraw()
        except tkinter.TclError:
            _redraws.remove(redraw)


def drag_to_scroll(text: tkinter.Text) -> None:
    '''In tablet mode a drag scrolls the text by as much as the finger moves, instead of
    selecting; a tap still places the cursor and a double tap selects a word.'''
    last = [0, 0]

    def press(event):
        last[:] = (event.x, event.y)

    def drag(event):
        if not enabled:
            return None
        (dx, dy) = (last[0] - event.x, last[1] - event.y)
        last[:] = (event.x, event.y)
        if dy:
            text.yview_scroll(dy, 'pixels')
        if dx:
            text.xview_scroll(dx, 'pixels')
        return 'break'

    text.bind('<ButtonPress-1>', press, add='+')
    text.bind('<B1-Motion>', drag, add='+')
    text.bind('<B1-Leave>', lambda _: 'break' if enabled else None, add='+')
