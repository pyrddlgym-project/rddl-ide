'''Stable-Baselines3 (through pyRDDLGym-rl) as a settings form, read from the installed
packages. The algorithms are those pyRDDLGym-rl finds in stable-baselines3 and
sb3-contrib.'''
import functools
from typing import Any, Dict, List

from pyRDDLGym_rl.core.env import SimplifiedActionRDDLEnv
from pyRDDLGym_rl.core.sb3_trainer import METHODS, StableBaselinesTrainer
from stable_baselines3.common.callbacks import BaseCallback

from rddl_ide.core.settings.introspect import signature_fields
from rddl_ide.core.settings.model import Field, FormState, Section
from rddl_ide.core.settings.provider import Provider, assign, read_config, write_config
from rddl_ide.core.statusbar import number

# arguments the IDE supplies, or that only make sense for the IDE to set
NOT_CONFIGURABLE_ALGORITHM = {'policy', 'env'}
NOT_CONFIGURABLE_TRAINER = {'env', 'method'}
NOT_CONFIGURABLE_TRAIN = {'callback'}
NOT_CONFIGURABLE_ENV = {'domain', 'instance', 'vectorized'}

# config section name of each form section
SECTION_NAMES = {'algorithm': 'Algorithm', 'trainer': 'Trainer', 'train': 'Train',
                 'environment': 'Environment'}


class StableBaselinesProvider(Provider):

    kind = 'sb3'
    title = 'Stable-Baselines3'

    def __init__(self) -> None:
        self._sections = [
            Section('algorithm', '[Algorithm]', chooser='method',
                    fields=lambda option, state: self._algorithm_fields(option),
                    options=lambda state: sorted(METHODS),
                    default_option=lambda state: 'ppo'),
            Section('trainer', '[Trainer]', fields=lambda option, state: signature_fields(
                StableBaselinesTrainer, NOT_CONFIGURABLE_TRAINER)),
            Section('train', '[Train]', fields=lambda option, state: signature_fields(
                StableBaselinesTrainer.train, NOT_CONFIGURABLE_TRAIN)),
            Section('environment', '[Environment]', fields=lambda option, state: signature_fields(
                SimplifiedActionRDDLEnv, NOT_CONFIGURABLE_ENV)),
        ]

    @functools.lru_cache(maxsize=None)
    def _algorithm_fields(self, option: str) -> List[Field]:
        return signature_fields(METHODS[option], NOT_CONFIGURABLE_ALGORITHM)

    def sections(self) -> List[Section]:
        return self._sections

    def to_config(self, state: FormState) -> str:
        algorithm = {'method': self.section('algorithm').option(state),
                     **self.changed(state, 'algorithm')}
        sections = [('Algorithm', algorithm)]
        sections += [(SECTION_NAMES[s], self.changed(state, s))
                     for s in ('trainer', 'train', 'environment')]
        return write_config(self.kind, sections)

    def from_config(self, text: str) -> FormState:
        values = read_config(text)
        state = FormState()
        algorithm = dict(values.get('Algorithm', {}))
        if 'method' in algorithm:
            self.section('algorithm').choose(state, str(algorithm.pop('method')).lower())
        assign(state, self.section('algorithm'), algorithm)
        for section_id in ('trainer', 'train', 'environment'):
            assign(state, self.section(section_id), values.get(SECTION_NAMES[section_id], {}))
        return state

    def env_args(self, state: FormState) -> Dict[str, Any]:
        return {'base_class': SimplifiedActionRDDLEnv, **self.changed(state, 'environment')}

    def build_policy(self, env, state: FormState, progress=None):
        trainer = StableBaselinesTrainer(
            env, self.section('algorithm').option(state),
            **self.changed(state, 'trainer'), **self.changed(state, 'algorithm'))
        callback = None if progress is None else _ReportTraining(progress)
        trainer.train(callback=callback, **self.changed(state, 'train'))
        return trainer.agent()


class _ReportTraining(BaseCallback):
    '''Reports the timesteps trained and the mean reward of the recent episodes.'''

    def __init__(self, progress) -> None:
        super().__init__()
        self.progress = progress

    def _on_training_start(self) -> None:
        self._start = self.model.num_timesteps  # of earlier training sessions
        self._total = self.locals['total_timesteps'] - self._start

    def _on_step(self) -> bool:
        self.progress.training(self._describe)
        return True

    def _describe(self) -> str:
        done = self.model.num_timesteps - self._start
        text = f'Training {100 * done // max(self._total, 1)}% · ' \
               f'timestep {done:,}/{self._total:,}'
        episodes = self.model.ep_info_buffer
        if episodes:
            mean = sum(episode['r'] for episode in episodes) / len(episodes)
            text += f' · mean episode reward {number(mean)}'
        return text
