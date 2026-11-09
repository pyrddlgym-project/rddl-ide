'''The status bar at the bottom of the window, which shows the progress of a run.'''
import os
import sys
import time
from importlib import metadata
from tkinter import TclError
from typing import Callable, Optional, Tuple

from customtkinter import CTkFont, CTkFrame, CTkLabel, ThemeManager

from rddl_ide.core.icons import Tooltip

REFRESH_SECONDS = 0.1
SEPARATOR = '   |   '
SEGMENT_PADDING = 12


def number(value) -> str:
    '''A metric (a float or a scalar array) with 5 significant digits.'''
    return f'{float(value):.5g}'


class RunStopped(BaseException):
    '''Raised by a progress report to end the run, when it was stopped.'''


def environment() -> Tuple[str, str]:
    '''The Python version, environment and pyRDDLGym version, short and in full.'''
    python = '.'.join(map(str, sys.version_info[:3]))
    name = os.environ.get('CONDA_DEFAULT_ENV')
    if name is None and sys.prefix != sys.base_prefix:
        name = os.path.basename(sys.prefix)
    try:
        pyrddlgym = f'pyRDDLGym {metadata.version("pyRDDLGym")}'
    except metadata.PackageNotFoundError:
        pyrddlgym = 'pyRDDLGym not installed'
    short = f'Python {python}' + (f' ({name})' if name else '') + f' · {pyrddlgym}'
    return (short, f'{sys.executable}\n{pyrddlgym}')


class StatusBar(CTkFrame):
    '''A line of text on the frame color with a hairline above it.'''

    def __init__(self, master):
        palette = ThemeManager.theme['Palette']
        super().__init__(master, corner_radius=0, fg_color=palette['chrome'])
        CTkFrame(self, height=1, corner_radius=0, fg_color=palette['border']).pack(
            side='top', fill='x')
        self._font = CTkFont(size=13)
        self._viewer = None
        (short, full) = environment()
        Tooltip(self._segment(short), full)
        self.newline = self._segment('')
        self.encoding = self._segment('')
        self.position = self._segment('')
        self.label = CTkLabel(self, text='Ready', anchor='w', padx=12, height=28,
                              text_color=palette['text'], font=self._font)
        self.label.pack(side='left', fill='x', expand=True)

    def _segment(self, text: str) -> CTkLabel:
        label = CTkLabel(
            self, text=text, padx=SEGMENT_PADDING, height=28,
            text_color=ThemeManager.theme['Palette']['text'], font=self._font)
        label.pack(side='right')
        return label

    def show(self, text: str) -> None:
        self.label.configure(text=text)

    def track(self, viewer) -> None:
        '''Shows the cursor position and file format of the code viewer.'''
        def update(_=None):
            self._viewer = viewer
            viewer.after_idle(self.update_position)
            
        def selected(_=None):
            if self._viewer is viewer:
                viewer.after_idle(self.update_position)

        for sequence in ('<FocusIn>', '<KeyRelease>', '<ButtonRelease-1>', '<<Undo>>',
                         '<<Redo>>', '<<TextReplaced>>'):
            viewer.bind(sequence, update, add='+')
        viewer.bind('<<Selection>>', selected, add='+')

    def update_position(self) -> None:
        '''Shows the cursor position of the viewer last used, if it is still shown.'''
        viewer = self._viewer
        try:
            if viewer is None or not viewer.winfo_viewable():
                for segment in (self.position, self.encoding, self.newline):
                    segment.configure(text='')
                return
            (line, column) = viewer.index('insert').split('.')
            text = f'Ln {line}, Col {int(column) + 1}'
            if viewer.tag_ranges('sel'):
                text += f' ({len(viewer.get("sel.first", "sel.last"))} selected)'
            (encoding, newline) = viewer.file_format.describe()
            self.position.configure(text=text)
            self.encoding.configure(text=encoding)
            self.newline.configure(text=newline)
        except TclError:
            pass


class RunProgress:
    '''Shows the progress of one run in a status bar.'''

    def __init__(self, bar: StatusBar):
        self.bar = bar
        self.note_text = self.training_text = self.episode_text = ''
        self._describe: Optional[Callable[[], str]] = None
        self._shown_at = 0.0
        self.stopped = False
        self.policy = None
        
    def stop(self) -> None:
        '''Ends the run at its next progress report.'''
        self.stopped = True

    def show_stopped(self) -> None:
        '''Shows that the run was stopped, with the progress it had made.'''
        self._update_training()
        parts = ['Stopped', self.episode_text, self.training_text]
        try:
            self.bar.show(SEPARATOR.join(part for part in parts if part))
        except TclError:
            pass

    def note(self, text: str) -> None:
        '''Shows what the run is doing until it reports progress.'''
        self.note_text = text
        self.refresh(force=True)

    def training(self, describe: Callable[[], str]) -> None:
        '''Reports the latest training metrics.'''
        self._describe = describe
        self.refresh()

    def step(self, step: int, horizon: int, reward, total,
             episode: Optional[Tuple[int, int]]=None) -> None:
        '''Reports a step of the episode, which is (number, of how many) if several.'''
        prefix = '' if episode is None else f'Episode {episode[0]}/{episode[1]} · '
        self.episode_text = f'{prefix}Step {step}/{horizon} · reward {number(reward)} · ' \
                            f'return {number(total)}'
        self.refresh()

    def finish(self, text: str) -> None:
        '''Shows how the episode ended, with the final training metrics.'''
        self.episode_text = text
        self.refresh(force=True)

    def refresh(self, force: bool=False) -> None:
        if self.stopped:
            raise RunStopped()
        now = time.monotonic()
        if not force and now - self._shown_at < REFRESH_SECONDS:
            return
        self._shown_at = now
        self._update_training()
        parts = [part for part in (self.episode_text, self.training_text) if part]
        try:
            self.bar.show(SEPARATOR.join(parts) if parts else self.note_text)
            self.bar.update()
        except TclError:
            self.stopped = True
        if self.stopped:
            raise RunStopped()

    def _update_training(self) -> None:
        '''Describes the latest training metrics reported, if not yet described.'''
        if self._describe is not None:
            try:
                self.training_text = self._describe()
            except Exception as error:
                self.training_text = f'training metrics unavailable ({type(error).__name__})'
            self._describe = None
