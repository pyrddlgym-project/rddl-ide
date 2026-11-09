import os
import shutil
import sys
import tempfile
import traceback
from tkinter import messagebox
from typing import NamedTuple, Optional

import pyRDDLGym
from pyRDDLGym.core.visualizer.movie import MovieGenerator

from rddl_ide.core.errorlocation import strip_ansi
from rddl_ide.core.statusbar import RunProgress, RunStopped, number

def policy_from_code(source):
    '''Runs the source of a custom policy, which must define build_policy(env) and
    required_env_args(), and returns those two functions.'''
    namespace = {'__name__': '__policy__'}
    exec(compile(source, '<policy>', 'exec'), namespace)
    return namespace['build_policy'], namespace['required_env_args']


VISUALIZERS = {'default': 'Default', 'chart': 'Chart', 'heatmap': 'Heatmap',
               'text': 'Text', 'none': 'None (faster)'}


class RunOptions(NamedTuple):
    '''How a policy is evaluated: the visualizer is a key of VISUALIZERS, where default
    is that of the domain in rddlrepository (else chart), and log_file the CSV file the
    states, actions and rewards are logged to, if any.'''
    episodes: int = 1
    seed: Optional[int] = None
    visualizer: str = 'default'
    log_file: Optional[str] = None
    enforce_constraints: bool = False


class _Episodes:
    '''Reports each step of the episodes, by wrapping the reset() and step() of the
    environment.'''

    def __init__(self, env, progress: RunProgress, episodes: int):
        self.episode, self.steps, self.total, self.discount = 0, 0, 0.0, 1.0
        (env_reset, env_step) = (env.reset, env.step)

        def reset(*args, **kwargs):
            self.episode += 1
            self.steps, self.total, self.discount = 0, 0.0, 1.0
            return env_reset(*args, **kwargs)

        def step(action):
            result = env_step(action)
            reward = float(result[1])
            self.steps += 1
            self.total += reward * self.discount
            self.discount *= env.discount
            progress.step(self.steps, env.horizon, reward, self.total,
                          (self.episode, episodes) if episodes > 1 else None)
            return result
        (env.reset, env.step) = (reset, step)


def _summary(episodes: _Episodes, stats, count: int) -> str:
    if count == 1:
        return f'Done · {episodes.steps} steps · return {number(episodes.total)}'
    return f'Done · {count} episodes · return {number(stats["mean"])} ' \
           f'± {number(stats["std"])} (min {number(stats["min"])}, ' \
           f'max {number(stats["max"])})'


def make_environment(domain, instance, required_env_args, viz,
                     options: RunOptions, log_path: str, record=None):
    '''The environment of a run of the RDDL texts, made with the arguments returned by
    required_env_args() and the options, and whether it is rendered.'''
    (domain_file, inst_file) = (os.path.join(os.path.dirname(log_path), name)
                                for name in ('domain.rddl', 'instance.rddl'))
    for (path, text) in ((domain_file, domain), (inst_file, instance)):
        with open(path, 'w', encoding='utf-8') as file:
            file.write(text)
    env_args = dict(required_env_args())
    if options.enforce_constraints:
        env_args['enforce_action_constraints'] = True
    if options.log_file:
        env_args['log_path'] = log_path
    env = pyRDDLGym.make(domain=domain_file, instance=inst_file, **env_args)
    try:
        render = options.visualizer != 'none' or record is not None
        if options.visualizer not in ('default', 'none'):
            viz = options.visualizer
        movie_gen = None
        if record is not None:
            movie_gen = MovieGenerator(record, env.model.domain_name, 9999)
        env.set_visualizer(viz, movie_gen=movie_gen)
    except BaseException:
        close_env(env)
        raise
    return (env, render)


def evaluate_policy(domain, instance, build_policy, required_env_args, viz, record,
                    progress: RunProgress, options: RunOptions=RunOptions()):
    '''Runs the episodes of the policy built by build_policy(env) on the RDDL texts, in
    an environment made
    with the arguments returned by required_env_args() and the options, showing their
    progress. viz is the visualizer of the domain in rddlrepository, if any.'''
    env = None
    with tempfile.TemporaryDirectory() as folder:
        log_path = os.path.join(folder, 'simulation')
        try:
            try:
                progress.note('Preparing the environment and the policy...')
                (env, render) = make_environment(domain, instance, required_env_args,
                                                 viz, options, log_path, record)
                policy = progress.policy = build_policy(env)
                episodes = _Episodes(env, progress, options.episodes)
                stats = policy.evaluate(env, episodes=options.episodes, verbose=True,
                                        render=render, seed=options.seed)
                env.close()
                env = None
                summary = _summary(episodes, stats, options.episodes)
                progress.finish(summary + save_log(log_path, options.log_file))
                return None
            except Exception as error:
                print(traceback.format_exc(), file=sys.stderr)
                close_env(env)
                env = None
                progress.finish('Stopped by an error' + save_log(log_path, options.log_file))
                message = str(error)
                messagebox.showerror('pyRDDLGym error', strip_ansi(message))
                return message
        except RunStopped:
            close_env(env)
            save_log(log_path, options.log_file)
            return None


def save_log(log_path, log_file) -> str:
    '''Moves the simulation log pyRDDLGym wrote to the file chosen, and says so.'''
    written = f'{log_path}_log.csv'
    if not log_file or not os.path.exists(written):
        return ''
    try:
        shutil.move(written, log_file)
    except OSError as error:
        return f' · could not save the log ({error.strerror})'
    return f' · log saved to {os.path.basename(log_file)}'


def close_env(env) -> None:
    '''Closes the environment (and its visualizer) of a run that did not finish.'''
    if env is not None:
        try:
            env.close()
        except Exception:
            pass
