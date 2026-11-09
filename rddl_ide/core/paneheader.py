'''The header above each pane (domain, instance, policy).'''
from typing import Callable, List, Tuple

from customtkinter import CTkButton, CTkFont, CTkFrame, CTkLabel, ThemeManager

from rddl_ide.core.icons import IconButton

GROUP_GAP = 10
KIND_GAP = 6
CRUMB_SEPARATOR = '›'


class PaneHeader(CTkFrame):
    '''A caption on the frame color with a hairline below it, icon buttons on the right.'''

    def __init__(self, master, text):
        palette = ThemeManager.theme['Palette']
        super().__init__(master, corner_radius=0, fg_color=palette['chrome'])
        CTkFrame(self, height=1, corner_radius=0, fg_color=palette['border']).pack(
            side='bottom', fill='x')
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
        self._caption(text)
        self.crumbs = CTkFrame(self, corner_radius=0, fg_color='transparent', height=30)
        self.crumbs.pack(side='left', fill='x', expand=True)
        self._crumb_texts = []
        self._crumb_actions = []
        self._gap = False

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
        button.pack(side='left', padx=(GROUP_GAP if self._gap else 0, 0))
        self._gap = False
        return button

    def add_gap(self) -> None:
        '''Separates the buttons added next from those added before.'''
        self._gap = True

    def _caption(self, text: str) -> None:
        '''Shows a caption 'Kind: rest' as the kind in bold followed by the rest.'''
        (kind, _, rest) = text.partition(': ')
        self.kind.configure(text=kind)
        self.label.configure(text=rest)

    def configure(self, require_redraw=False, **kwargs):
        if 'text' in kwargs:
            self._caption(kwargs.pop('text'))
        super().configure(require_redraw=require_redraw, **kwargs)
