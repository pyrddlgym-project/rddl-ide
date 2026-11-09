'''The keyboard shortcuts of the window, e.g. Ctrl+S, with the text that the menus show
for them.'''
import sys
from typing import Callable, Dict, Tuple

MAC = sys.platform == 'darwin'
WINDOWS = sys.platform.startswith('win')

# masks of the modifiers in the state of a Tk key event
SHIFT = 0x1
CONTROL = 0x8 if MAC else 0x4  # Command on macOS
ALT = 0x10 if MAC else (0x20000 if WINDOWS else 0x8)  # Option on macOS

Key = Tuple[bool, bool, bool, str]


def label(key: str, control: bool=False, shift: bool=False, alt: bool=False) -> str:
    '''The text of a shortcut, e.g. Ctrl+Shift+S (or ⇧⌘S on macOS).'''
    name = key.upper() if len(key) == 1 else key
    if MAC:
        return ('⌥' if alt else '') + ('⇧' if shift else '') + \
            ('⌘' if control else '') + name
    return ''.join(part + '+' for (part, on) in
                   (('Ctrl', control), ('Alt', alt), ('Shift', shift)) if on) + name


class Shortcuts:
    '''Runs a command when its shortcut is pressed in the window.'''

    def __init__(self, window):
        self.window = window
        self._commands: Dict[Key, Callable[[], None]] = {}
        window.bind_all('<KeyPress>', self.dispatch, add='+')

    def add(self, command: Callable[[], None], key: str, control: bool=False,
            shift: bool=False, alt: bool=False) -> str:
        '''Runs the command on the shortcut, and returns the text of the shortcut.'''
        self._commands[(control, alt, shift, key.lower())] = command
        return label(key, control, shift, alt)

    def attach(self, viewer) -> None:
        '''Gives the shortcuts precedence over the key bindings of a code viewer.'''
        viewer.bind('<KeyPress>', self.dispatch, add='+')

    def dispatch(self, event):
        '''Runs the command of the key pressed, if it is a shortcut of the window.'''
        try:
            if event.widget.winfo_toplevel() is not self.window:
                return None
        except (AttributeError, KeyError):
            return None
        control = bool(event.state & CONTROL)
        alt = bool(event.state & ALT)
        if WINDOWS and control and alt:
            return None
        command = self._commands.get(
            (control, alt, bool(event.state & SHIFT), event.keysym.lower()))
        if command is None:
            return None
        try:
            command()
        except Exception:
            self.window.report_callback_exception(*sys.exc_info())
        return 'break'
