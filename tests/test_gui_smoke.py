'''A smoke test of the GUI on the platform it runs on: it builds the IDE's window and
drives the menus, choosers and theme switch, failing on any error, including errors
raised in Tk callbacks (which Tk only prints). It needs a display (on Linux CI, run it
under xvfb-run) and is skipped without one.'''
import time
import tkinter
import unittest
import warnings

from customtkinter import get_appearance_mode, set_appearance_mode

from rddl_ide.core.codearea import CTkCodeViewer, LineNumbers
from rddl_ide.core.popup import ChoiceMenu, MenuBarMenu, PopupMenu

try:
    tkinter.Tk().destroy()
    DISPLAY = True
except tkinter.TclError:
    DISPLAY = False

DOMAIN = '''domain smoke {
    pvariables {
        x : { state-fluent, int, default = 0 };
        a : { action-fluent, bool, default = false };
    };
    cpfs {
        x' = x + 1;
    };
    reward = x;
}
'''


@unittest.skipUnless(DISPLAY, 'no display')
class TestGuiSmoke(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings('ignore')
        from rddl_ide.run import create_window
        set_appearance_mode('light')
        self.popups = []
        original = PopupMenu.__init__

        def record(popup, *args, **kwargs):
            self.popups.append(popup)
            original(popup, *args, **kwargs)

        PopupMenu.__init__ = record
        self.addCleanup(setattr, PopupMenu, '__init__', original)
        MenuBarMenu._menus.clear()

        (self.window, self.domain, self.instance, self.policy) = create_window()
        self.errors = []
        self.window.report_callback_exception = \
            lambda kind, error, trace: self.errors.append(error)
        self.addCleanup(self.window.destroy)
        self.pump(0.5)

    def tearDown(self):
        self.assertEqual(self.errors, [], 'errors in Tk callbacks')

    def pump(self, seconds=0.1):
        end = time.time() + seconds
        while time.time() < end:
            self.window.update()
            time.sleep(0.01)

    def widgets(self, kind, root=None):
        found = []
        for child in (root or self.window).winfo_children():
            if isinstance(child, kind):
                found.append(child)
            found.extend(self.widgets(kind, child))
        return found

    def open_popup(self, open_it) -> PopupMenu:
        count = len(self.popups)
        open_it()
        self.pump(0.3)
        self.assertEqual(len(self.popups), count + 1, 'no popup opened')
        popup = self.popups[-1]
        self.assertFalse(popup.closed)
        self.assertTrue(popup.window.winfo_viewable())
        self.assertIs(self.window.grab_current(), popup.window, 'the popup has no grab')
        return popup

    def choose(self, popup, label):
        '''Clicks the row of the item, as the pointer would.'''
        (top, bottom, _) = next(row for row in popup.rows if popup.items[row[2]][0] == label)
        popup._reveal(next(row[2] for row in popup.rows if popup.items[row[2]][0] == label))
        x = popup.canvas.winfo_rootx() + 20
        y = popup.canvas.winfo_rooty() + (top + bottom) // 2 - int(popup.canvas.canvasy(0))
        for event in ('<ButtonPress-1>', '<ButtonRelease-1>'):
            popup.window.event_generate(event, x=0, y=0, rootx=x, rooty=y)
            self.pump(0.05)
        self.pump(0.3)
        self.assertTrue(popup.closed)

    def menu(self, title) -> MenuBarMenu:
        return next(menu for menu in MenuBarMenu._menus if menu.button.cget('text') == title)

    def test_menus_choosers_and_themes(self):
        # every menu opens as a popup and closes on Escape
        for title in ('Domain', 'Instance', 'Edit', 'Agent', 'View'):
            popup = self.open_popup(self.menu(title).open)
            popup.window.event_generate('<Escape>')
            self.pump(0.2)
            self.assertTrue(popup.closed, title)

        # the editors show line numbers and mark errors
        editor = self.domain.editor.text
        editor.insert('1.0', DOMAIN)
        editor.apply()
        editor.show_error('7.8', '7.18')
        self.pump(0.3)
        gutter = self.widgets(LineNumbers, self.domain)[0]
        self.assertIn('1', [gutter.itemcget(item, 'text') for item in gutter.find_all()])

        # the theme switch, from the View menu
        before = get_appearance_mode()
        self.choose(self.open_popup(self.menu('View').open), 'Toggle Light/Dark Theme')
        self.pump(0.5)
        self.assertNotEqual(get_appearance_mode(), before)

        # the baselines' forms load from the Agent menu, and their choosers work
        for baseline in ('JaxPlan (offline)', 'Built-in agent'):
            self.choose(self.open_popup(self.menu('Agent').open), baseline)
            self.pump(0.5)
            if self.policy.mode != 'form':  # the baseline's package is not installed
                continue
            chooser = self.widgets(ChoiceMenu, self.policy)[0]
            options = chooser._values
            self.choose(self.open_popup(chooser._open_dropdown_menu), options[-1])
            self.pump(0.5)
            chooser = self.widgets(ChoiceMenu, self.policy)[0]  # the form was redrawn
            self.assertEqual(chooser.get(), options[-1])

        # back to the other theme, with everything drawn
        self.choose(self.open_popup(self.menu('View').open), 'Toggle Light/Dark Theme')
        self.pump(0.5)
        self.assertEqual(get_appearance_mode(), before)
        self.assertTrue(self.widgets(CTkCodeViewer))


if __name__ == '__main__':
    unittest.main()
