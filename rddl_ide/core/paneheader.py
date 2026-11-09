'''The header above each pane (domain, instance, policy).'''
from customtkinter import CTkFont, CTkFrame, CTkLabel, ThemeManager

from rddl_ide.core.icons import IconButton

GROUP_GAP = 10


class PaneHeader(CTkFrame):
    '''A caption on the frame color with a hairline below it, icon buttons on the right.'''

    def __init__(self, master, text):
        palette = ThemeManager.theme['Palette']
        super().__init__(master, corner_radius=0, fg_color=palette['chrome'])
        CTkFrame(self, height=1, corner_radius=0, fg_color=palette['border']).pack(
            side='bottom', fill='x')
        self.tools = CTkFrame(self, corner_radius=0, fg_color='transparent')
        self.tools.pack(side='right', padx=(0, 4))
        self.label = CTkLabel(self, text=text, anchor='w', padx=12, height=30,
                              text_color=palette['text'], font=CTkFont(size=13))
        self.label.pack(side='left', fill='x', expand=True)
        self._gap = False

    def add_button(self, icon, tooltip, command, **kwargs) -> IconButton:
        '''Adds a button after those added before.'''
        button = IconButton(self.tools, icon, tooltip, command, **kwargs)
        button.pack(side='left', padx=(GROUP_GAP if self._gap else 0, 0))
        self._gap = False
        return button

    def add_gap(self) -> None:
        '''Separates the buttons added next from those added before.'''
        self._gap = True

    def configure(self, require_redraw=False, **kwargs):
        if 'text' in kwargs:
            self.label.configure(text=kwargs.pop('text'))
        super().configure(require_redraw=require_redraw, **kwargs)
