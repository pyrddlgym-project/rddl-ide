'''The header above each pane (domain, instance, policy).'''
from customtkinter import CTkFont, CTkFrame, CTkLabel, ThemeManager


class PaneHeader(CTkFrame):
    '''A caption on the frame color with a hairline below it.'''

    def __init__(self, master, text):
        palette = ThemeManager.theme['Palette']
        super().__init__(master, corner_radius=0, fg_color=palette['chrome'])
        self.label = CTkLabel(self, text=text, anchor='w', padx=12, height=30,
                              text_color=palette['text'], font=CTkFont(size=13))
        self.label.pack(side='top', fill='x')
        CTkFrame(self, height=1, corner_radius=0, fg_color=palette['border']).pack(
            side='top', fill='x')

    def configure(self, require_redraw=False, **kwargs):
        if 'text' in kwargs:
            self.label.configure(text=kwargs.pop('text'))
        super().configure(require_redraw=require_redraw, **kwargs)
