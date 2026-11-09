'''A small window of labelled fields with its buttons at the bottom right, in the style
of the main window, e.g. to load a problem from rddlrepository.'''
from typing import Callable

from customtkinter import CTkButton, CTkFrame, CTkLabel, CTkToplevel, ThemeManager

from rddl_ide.core.appicon import set_icon
from rddl_ide.core.titlebar import match_title_bar

FIELD_WIDTH = 280
BUTTON_WIDTH = 90
PADDING = 16


class Dialog(CTkToplevel):
    '''Add fields with field(label, widget), whose widgets are made in body, then the
    buttons with buttons(text, action); Enter does the action and Escape closes.'''

    def __init__(self, master, title: str):
        super().__init__(master, fg_color=ThemeManager.theme['Palette']['content'])
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.after(250, lambda: set_icon(self))
        match_title_bar(self, 'content')
        self.body = CTkFrame(self, fg_color='transparent')
        self.body.grid(row=0, column=0, sticky='nsew', padx=PADDING, pady=(PADDING, 8))
        self.body.columnconfigure(1, weight=1)
        self._rows = 0
        self.bind('<Escape>', lambda _: self.destroy())

    def field(self, label: str, widget):
        '''Shows the widget, made in body, with the label on its left.'''
        CTkLabel(self.body, text=label, anchor='w').grid(
            row=self._rows, column=0, sticky='w', padx=(0, 12), pady=4)
        widget.configure(width=FIELD_WIDTH)
        widget.grid(row=self._rows, column=1, sticky='ew', pady=4)
        self._rows += 1
        return widget

    def buttons(self, text: str, action: Callable[[], None]) -> None:
        '''Shows Cancel and the button doing the action.'''
        row = CTkFrame(self, fg_color='transparent')
        row.grid(row=1, column=0, sticky='e', padx=PADDING, pady=(8, PADDING))
        CTkButton(row, text='Cancel', width=BUTTON_WIDTH, fg_color='transparent',
                  hover_color=ThemeManager.theme['Palette']['hover'],
                  command=self.destroy).pack(side='left', padx=(0, 8))
        CTkButton(row, text=text, width=BUTTON_WIDTH, command=action).pack(side='left')
        self.bind('<Return>', lambda _: action())
        self.after(100, self.focus_force)
