'''The header above each pane (domain, instance, policy).'''
import re
from tkinter import TclError, font
from typing import Callable, List, Tuple

from customtkinter import CTkButton, CTkFont, CTkFrame, CTkLabel, ThemeManager

from rddl_ide.core.icons import IconButton, Tooltip
from rddl_ide.core.popup import SEPARATOR, PopupMenu

GROUP_GAP = 10
KIND_GAP = 6
CRUMB_SEPARATOR = '›'
ELLIPSIS = '…'
MIN_CAPTION = 90


class PaneHeader(CTkFrame):
    '''A caption on the frame color with a hairline below it, icon buttons on the right.'''

    def __init__(self, master, text):
        palette = ThemeManager.theme['Palette']
        super().__init__(master, corner_radius=0, fg_color=palette['chrome'])
        self.line = CTkFrame(self, height=1, corner_radius=0, fg_color=palette['border'])
        self.line.pack(side='bottom', fill='x', pady=(1, 0))  # as high as when active
        self.active = False
        self.tools = CTkFrame(self, corner_radius=0, fg_color='transparent')
        self.tools.pack(side='right', padx=(0, 4))
        self._font = CTkFont(size=13)
        self.kind = CTkLabel(self, text='', anchor='w', padx=0, height=30,
                             text_color=palette['text'],
                             font=CTkFont(size=13, weight='bold'))
        self.kind.pack(side='left', padx=(6, KIND_GAP))
        self.label = CTkLabel(self, text='', anchor='w', padx=0, height=30,
                              text_color=palette['text'], font=self._font)
        self.label.pack(side='left')
        self._rest = ''
        self._fit_pending = None
        self._full_caption = Tooltip(self.label, '')
        self._full_kind = Tooltip(self.kind, '')
        self._caption(text)
        self.dot = CTkLabel(self, text='●', anchor='w', padx=0, width=0, height=30,
                            text_color=palette['text'], font=CTkFont(size=10))
        self.crumbs = CTkFrame(self, corner_radius=0, fg_color='transparent', height=30)
        self.crumbs.pack(side='left', fill='x', expand=True)
        self._crumb_texts = []
        self._crumb_actions = []
        self._gap = False
        self._buttons = []
        self._hidden = 0
        self.more = IconButton(self.tools, 'more', 'More actions', self._open_more)
        self.bind('<Configure>', self._schedule_fit, add='+')

    def set_active(self, active: bool) -> None:
        '''Underlines the header in the accent color while its pane is the one the
        keyboard shortcuts act on.'''
        if active != self.active:
            self.active = active
            palette = ThemeManager.theme['Palette']
            self.line.configure(height=2 if active else 1,
                                fg_color=palette['accent' if active else 'border'])
            gap = round(self._apply_widget_scaling(1))
            self.line.pack_configure(pady=0 if active else (gap, 0))

    def set_modified(self, modified: bool) -> None:
        '''Shows a dot after the caption while what the pane shows has unsaved changes.'''
        if modified and not self.dot.winfo_ismapped():
            self.dot.pack(side='left', after=self.label, padx=(6, 0))
            self._schedule_fit()
        elif not modified and self.dot.winfo_ismapped():
            self.dot.pack_forget()
            self._schedule_fit()

    def set_crumbs(self, crumbs: List[Tuple[str, Callable[[], None]]]) -> None:
        '''Shows the breadcrumb after the caption: (text, action on a click) of each part.
        The parts are only made again when their texts change.'''
        self._crumb_actions = [action for (_, action) in crumbs]
        texts = [text for (text, _) in crumbs]
        if texts == self._crumb_texts:
            return
        self._crumb_texts = texts
        for child in self.crumbs.winfo_children():
            child.destroy()
        palette = ThemeManager.theme['Palette']
        for (i, text) in enumerate(texts):
            CTkLabel(self.crumbs, text=CRUMB_SEPARATOR, width=0, padx=0, height=30,
                     text_color=palette['text_muted'], font=self._font).pack(
                side='left', padx=(8 if i == 0 else 2, 2))
            CTkButton(self.crumbs, text=text, width=0, height=24, corner_radius=4,
                      border_spacing=4, fg_color='transparent',
                      hover_color=palette['hover'], text_color=palette['text'],
                      font=self._font, command=lambda i=i: self._crumb_actions[i]()).pack(
                side='left')

    def add_button(self, icon, tooltip, command, **kwargs) -> IconButton:
        '''Adds a button after those added before.'''
        button = IconButton(self.tools, icon, tooltip, command, **kwargs)
        self._buttons.append((button, tooltip, command, self._gap))
        self._gap = False
        self._show_buttons(self._hidden)
        self._schedule_fit()
        return button

    def add_gap(self) -> None:
        '''Separates the buttons added next from those added before.'''
        self._gap = True

    def _caption(self, text: str) -> None:
        '''Shows a caption 'Kind: rest' as the kind in bold followed by the rest.'''
        (kind, _, rest) = text.partition(': ')
        self.kind.configure(text=kind)
        self._rest = rest
        self.label.configure(text=rest)
        self._schedule_fit()

    # ===========================================================================
    # fitting a narrow pane: the caption is shortened, then the first buttons are
    # moved into the menu of a '…' button
    # ===========================================================================

    def _show_buttons(self, hidden: int) -> None:
        '''Shows the buttons after the first hidden ones, and the more button in place of
        those if there are any.'''
        self._hidden = hidden
        for widget in self.tools.winfo_children():
            widget.pack_forget()
        if hidden:
            self.more.pack(side='left')
        for (i, (button, _, _, gap)) in enumerate(self._buttons[hidden:]):
            spaced = hidden > 0 if i == 0 else gap
            button.pack(side='left', padx=(GROUP_GAP if spaced else 0, 0))

    def _tools_width(self, hidden: int) -> int:
        gap = round(self._apply_widget_scaling(GROUP_GAP))
        shown = self._buttons[hidden:]
        width = sum(button.winfo_reqwidth() for (button, _, _, _) in shown)
        width += gap * sum(1 for (i, (_, _, _, has)) in enumerate(shown) if has and i > 0)
        if hidden:
            width += self.more.winfo_reqwidth() + (gap if shown else 0)
        return width

    def _open_more(self) -> None:
        '''Lists the hidden buttons, those disabled muted.'''
        items, disabled = [], []
        for (i, (button, tooltip, command, gap)) in enumerate(self._buttons[:self._hidden]):
            if gap and i > 0:
                items.append(SEPARATOR)
            match = re.fullmatch(r'(.*) \(([^()]+)\)', tooltip)
            items.append((match.group(1), command, match.group(2)) if match
                         else (tooltip, command))
            if button.cget('state') == 'disabled':
                disabled.append(len(items) - 1)
        PopupMenu(self.more, items, disabled=disabled)

    def _schedule_fit(self, _=None) -> None:
        if self._fit_pending is None:
            self._fit_pending = self.after_idle(self._fit)

    def _fit(self) -> None:
        '''Shortens the caption with an ellipsis when it would run under the buttons,
        down to MIN_CAPTION, and then hides the first buttons that do not fit. The
        breadcrumb after the caption gives way first.'''
        self._fit_pending = None
        try:
            if not self.winfo_ismapped():
                return
            scale = lambda value: round(self._apply_widget_scaling(value))
            measure = font.Font(font=self.label._label.cget('font')).measure
            room = self.winfo_width() - self.kind.winfo_reqwidth() - scale(6 + KIND_GAP) \
                - scale(4) - scale(GROUP_GAP)
            if self.dot.winfo_ismapped():
                room -= self.dot.winfo_reqwidth() + scale(6)
            caption = min(measure(self._rest), scale(MIN_CAPTION))
            hidden = 0
            while hidden < len(self._buttons) and \
                    self._tools_width(hidden) > room - caption:
                hidden += 1
            if hidden != self._hidden:
                self._show_buttons(hidden)
            room -= self._tools_width(hidden)
            text = self._rest
            if measure(text) > room:
                while text and measure(text + ELLIPSIS) > room:
                    text = text[:-1]
                text = text.rstrip() + ELLIPSIS if text else ''
            if text != self.label.cget('text'):
                self.label.configure(text=text)
            full = self._rest if text != self._rest else ''
            self._full_caption.text = self._full_kind.text = full
        except TclError:
            pass

    def configure(self, require_redraw=False, **kwargs):
        if 'text' in kwargs:
            self._caption(kwargs.pop('text'))
        super().configure(require_redraw=require_redraw, **kwargs)
