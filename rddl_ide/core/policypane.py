'''The policy pane: a settings form for a built-in baseline, or a code editor for a
custom Python policy.'''
import os

from customtkinter import CTkFrame, CTkLabel

from rddl_ide.core.codearea import CodeEditor
from rddl_ide.core.execution import policy_from_code
from rddl_ide.core.form import SettingsForm
from rddl_ide.core.paneheader import PaneHeader
from rddl_ide.core.settings import registry
from rddl_ide.core import textfile
from rddl_ide.core.textfile import FileFormat


class PolicyPane(CTkFrame):

    def __init__(self, master):
        super().__init__(master, corner_radius=0)
        self.header = PaneHeader(self, 'Policy')
        self.header.pack(side='top', fill='x')
        self.code_frame = CTkFrame(self, corner_radius=0, fg_color='transparent')
        self.text = CodeEditor(self.code_frame, language='python').text
        self.body = None
        self.mode = None  # 'code', 'form' or 'unavailable'
        self.provider = self.state = None
        self.changed = []  # called when the policy shown changes

    def _changed(self):
        for callback in self.changed:
            callback()

    def title(self, text):
        self.header.configure(text=text)

    def _clear(self):
        if self.body is not None:
            self.body.destroy()
            self.body = None
        self.code_frame.pack_forget()
        self.provider = self.state = None

    def show_code(self, source, caption, file_format=FileFormat()):
        self._clear()
        self.mode = 'code'
        self.text.set_text(source, file_format)
        self.code_frame.pack(fill='both', expand=True)
        self.title(f'Policy: {caption}')
        self._changed()

    def show_form(self, kind, provider=None, state=None):
        self._clear()
        self.title(f'Policy: {registry.title_of(kind)}')
        try:
            provider = registry.create(kind) if provider is None else provider
            state = provider.initial_state() if state is None else state
        except Exception as error:
            self.mode = 'unavailable'
            self.body = CTkLabel(self, text=f'{registry.title_of(kind)} is not available:\n\n'
                                            f'{type(error).__name__}: {error}',
                                 justify='left', anchor='nw', wraplength=500)
            self.body.pack(fill='both', expand=True, padx=12, pady=12)
            self._changed()
            return
        self.mode = 'form'
        self.provider, self.state = provider, state
        self.body = SettingsForm(self, provider, state)
        self.body.pack(fill='both', expand=True)
        self._changed()

    # ===========================================================================
    # files
    # ===========================================================================

    def default_extension(self):
        return '.cfg' if self.mode == 'form' else '.py'

    def save(self, path):
        if self.mode == 'form':
            content = self.provider.to_config(self.state)
            textfile.write(path, content, FileFormat())
        elif self.mode == 'code':
            self.text.file_format = textfile.write(path, self.text.content(),
                                                   self.text.file_format)
        else:
            raise RuntimeError('There is no policy to save.')

    def load(self, path):
        (content, file_format) = textfile.read(path)
        if not path.lower().endswith('.cfg'):
            self.show_code(content, os.path.basename(path), file_format)
            return
        kind = registry.detect_kind(content)
        if kind is None:
            raise ValueError(f'{os.path.basename(path)} is not a config of any of the '
                             f'baselines: its sections are not recognized.')
        provider = registry.create(kind)
        self.show_form(kind, provider, provider.from_config(content))
        self.title(f'Policy: {registry.title_of(kind)} ({os.path.basename(path)})')

    # ===========================================================================
    # running
    # ===========================================================================

    def policy(self, progress=None):
        '''Returns build_policy(env) and required_env_args() for the policy shown; a
        baseline reports its training to progress, a RunProgress, if given.'''
        if self.mode == 'form':
            provider, state = self.provider, self.state
            return (lambda env: provider.build_policy(env, state, progress),
                    lambda: provider.env_args(state))
        if self.mode == 'code':
            return policy_from_code(self.text.get('1.0', 'end'))
        raise RuntimeError('The selected policy is not available.')
