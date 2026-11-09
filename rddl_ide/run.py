import os
from tkinter import PanedWindow, TclError
from customtkinter import (
    AppearanceModeTracker, CTk, CTkFrame, ThemeManager, set_appearance_mode,
    set_default_color_theme
)
from CTkMenuBar import CTkMenuBar

from rddl_ide.core.appicon import set_icon
from rddl_ide.core import outline
from rddl_ide.core.codearea import CodeEditor
from rddl_ide.core.menubar import assign_menubar_functions
from rddl_ide.core.paneheader import PaneHeader
from rddl_ide.core.policypane import PolicyPane
from rddl_ide.core.statusbar import StatusBar
from rddl_ide.core.titlebar import match_title_bar

_HERE = os.path.dirname(os.path.abspath(__file__))
BREADCRUMB_DELAY = 100


class EditorPane(CTkFrame):
    '''A code editor with a header naming what it is editing, followed by a breadcrumb.'''

    def __init__(self, master, language, caption):
        super().__init__(master, corner_radius=0)
        self.header = PaneHeader(self, caption)
        self.header.pack(side='top', fill='x')
        self.editor = CodeEditor(self, language=language)
        self._pending = None
        text = self.editor.text
        for sequence in ('<KeyRelease>', '<ButtonRelease-1>', '<<Undo>>', '<<Redo>>',
                         '<<TextReplaced>>'):
            text.bind(sequence, self._schedule_crumbs, add='+')

    def _schedule_crumbs(self, _=None):
        '''Updates the breadcrumb once typing or moving pauses, as it reads the text.'''
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = self.after(BREADCRUMB_DELAY, self._update_crumbs)

    def _update_crumbs(self):
        self._pending = None
        text = self.editor.text
        source = text.content()
        cursor = len(text.get('1.0', 'insert'))
        self.header.set_crumbs([
            (crumb.text, lambda offset=crumb.offset: self._go_to(source, offset))
            for crumb in outline.crumbs(source, cursor)
        ])

    def _go_to(self, source, offset):
        text = self.editor.text
        index = outline.line_column(source, offset)
        text.mark_set('insert', index)
        text.tag_remove('sel', '1.0', 'end')
        text.see(index)
        text.focus_set()
        self._schedule_crumbs()

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
    match_title_bar(window)
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    window.geometry(f'{int(screen_w * 0.8)}x{int(screen_h * 0.8)}')
    window.after(0, lambda: _maximize(window))
    palette = ThemeManager.theme['Palette']
    menu = CTkMenuBar(window, bg_color=palette['chrome'], padx=2, pady=3)

    # domain on the left, instance above policy on the right, with draggable dividers
    status_bar = StatusBar(window)
    status_bar.pack(side='bottom', fill='x')
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
    def recolor(_):
        window.after_idle(color_dividers)
    AppearanceModeTracker.add(recolor, window)
    window.bind('<Destroy>', 
                lambda event: event.widget is window and
                    AppearanceModeTracker.remove(recolor), add='+')

    # size the panes once the window has been maximized
    def place_dividers():
        window.update_idletasks()
        panes.sash_place(0, int(panes.winfo_width() * 0.6), 0)
        right_panes.sash_place(0, 0, right_panes.winfo_height() // 2)
    window.after(200, place_dividers)

    assign_menubar_functions(menu, window, domain_pane, inst_pane, policy_pane,
                             domain_pane.editor.text, inst_pane.editor.text, status_bar)
    return window, domain_pane, inst_pane, policy_pane


def main():
    set_appearance_mode("system")
    create_window()[0].mainloop()


if __name__ == '__main__':
    main()
