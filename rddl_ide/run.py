import os
from tkinter import PanedWindow, TclError
from customtkinter import (
    AppearanceModeTracker, CTk, CTkFrame, ThemeManager, set_appearance_mode,
    set_default_color_theme
)
from CTkMenuBar import CTkMenuBar

from rddl_ide.core.appicon import set_icon
from rddl_ide.core.codearea import CodeEditor
from rddl_ide.core.menubar import assign_menubar_functions
from rddl_ide.core.paneheader import PaneHeader
from rddl_ide.core.policypane import PolicyPane

_HERE = os.path.dirname(os.path.abspath(__file__))


class EditorPane(CTkFrame):
    '''A code editor with a header naming what it is editing.'''

    def __init__(self, master, language, caption):
        super().__init__(master, corner_radius=0)
        self.header = PaneHeader(self, caption)
        self.header.pack(side='top', fill='x')
        self.editor = CodeEditor(self, language=language)

    def title(self, text):
        self.header.configure(text=text)


def _maximize(window):
    try:
        window.state('zoomed')  # Windows and macOS
    except TclError:
        window.attributes('-zoomed', True)  # X11


def create_window():
    '''Builds the IDE's window; returns it with its domain, instance and policy panes.'''
    set_default_color_theme(os.path.join(_HERE, "theme.json"))
    window = CTk()
    window.title('RDDL IDE')
    set_icon(window)
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    window.geometry(f'{int(screen_w * 0.8)}x{int(screen_h * 0.8)}')
    window.after(0, lambda: _maximize(window))
    palette = ThemeManager.theme['Palette']
    menu = CTkMenuBar(window, bg_color=palette['chrome'], padx=2, pady=3)

    # domain on the left, instance above policy on the right, with draggable dividers
    divider = window._apply_appearance_mode(ThemeManager.theme['CTk']['fg_color'])
    panes = PanedWindow(window, orient='horizontal', sashwidth=6, bd=0, bg=divider)
    panes.pack(fill='both', expand=True)
    domain_pane = EditorPane(panes, 'rddl', 'Domain: Untitled')
    right_panes = PanedWindow(panes, orient='vertical', sashwidth=6, bd=0, bg=divider)
    inst_pane = EditorPane(right_panes, 'rddl', 'Instance: Untitled')
    policy_pane = PolicyPane(right_panes)
    panes.add(domain_pane, minsize=200, stretch='always')
    panes.add(right_panes, minsize=200, stretch='always')
    right_panes.add(inst_pane, minsize=100, stretch='always')
    right_panes.add(policy_pane, minsize=100, stretch='always')

    def color_dividers(*_):
        color = window._apply_appearance_mode(ThemeManager.theme['CTk']['fg_color'])
        for paned in (panes, right_panes):
            paned.configure(bg=color)
    AppearanceModeTracker.add(lambda _: window.after_idle(color_dividers), window)

    # size the panes once the window has been maximized
    def place_dividers():
        window.update_idletasks()
        panes.sash_place(0, int(panes.winfo_width() * 0.6), 0)
        right_panes.sash_place(0, 0, right_panes.winfo_height() // 2)
    window.after(200, place_dividers)

    assign_menubar_functions(menu, window, domain_pane, inst_pane, policy_pane,
                             domain_pane.editor.text, inst_pane.editor.text)
    return window, domain_pane, inst_pane, policy_pane


def main():
    set_appearance_mode("system")
    create_window()[0].mainloop()


if __name__ == '__main__':
    main()
