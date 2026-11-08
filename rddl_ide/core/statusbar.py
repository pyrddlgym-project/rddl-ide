'''The status bar at the bottom of the window, which shows the progress of a run: the
training metrics of a planner or learner, and the step and return of the episode.'''
import time
from tkinter import TclError
from typing import Callable, Optional

from customtkinter import CTkFont, CTkFrame, CTkLabel, ThemeManager

REFRESH_SECONDS = 0.1  # during a run, the window is redrawn at most this often
SEPARATOR = '   |   '  # between the episode and the training parts of the text


def number(value) -> str:
    '''A metric (a float or a scalar array) with 5 significant digits.'''
    return f'{float(value):.5g}'


class RunStopped(BaseException):
    '''Raised by a progress report to end the run, when it was stopped (by closing the
    window); not an Exception, so that the code it passes through does not handle it.'''


class StatusBar(CTkFrame):
    '''A line of text on the frame color with a hairline above it.'''

    def __init__(self, master):
        palette = ThemeManager.theme['Palette']
        super().__init__(master, corner_radius=0, fg_color=palette['chrome'])
        CTkFrame(self, height=1, corner_radius=0, fg_color=palette['border']).pack(
            side='top', fill='x')
        self.label = CTkLabel(self, text='Ready', anchor='w', padx=12, height=28,
                              text_color=palette['text'], font=CTkFont(size=13))
        self.label.pack(side='top', fill='x')

    def show(self, text: str) -> None:
        self.label.configure(text=text)


class RunProgress:
    '''Shows the progress of one run in a status bar. The policy reports its training
    with training(describe), and the episode reports each step with step(). The window
    is redrawn at most every REFRESH_SECONDS, which also keeps it responding while the
    run blocks the event loop.'''

    def __init__(self, bar: StatusBar):
        self.bar = bar
        self.note_text = self.training_text = self.episode_text = ''
        self._describe: Optional[Callable[[], str]] = None
        self._shown_at = 0.0
        self.stopped = False
        self.policy = None  # once built

    def stop(self) -> None:
        '''Ends the run at its next progress report.'''
        self.stopped = True

    def show_stopped(self) -> None:
        '''Shows that the run was stopped, with the progress it had made.'''
        self._update_training()
        parts = ['Stopped', self.episode_text, self.training_text]
        try:
            self.bar.show(SEPARATOR.join(part for part in parts if part))
        except TclError:  # the window was destroyed
            pass

    def note(self, text: str) -> None:
        '''Shows what the run is doing until it reports progress.'''
        self.note_text = text
        self.refresh(force=True)

    def training(self, describe: Callable[[], str]) -> None:
        '''Reports the latest training metrics: describe() returns their text, and is
        only called if they are shown, as training can report thousands of times a
        second.'''
        self._describe = describe
        self.refresh()

    def step(self, step: int, horizon: int, reward, total) -> None:
        self.episode_text = f'Step {step}/{horizon} · reward {number(reward)} · ' \
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
        except TclError:  # the window was destroyed while it handled events
            self.stopped = True
        if self.stopped:  # e.g. while handling events
            raise RunStopped()

    def _update_training(self) -> None:
        '''Describes the latest training metrics reported, if not yet described.'''
        if self._describe is not None:
            try:
                self.training_text = self._describe()
            except Exception as error:  # the run goes on without the metrics
                self.training_text = f'training metrics unavailable ({type(error).__name__})'
            self._describe = None
