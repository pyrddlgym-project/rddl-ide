import re
import sys
import traceback
from tkinter import messagebox

import pyRDDLGym
from pyRDDLGym.core.visualizer.movie import MovieGenerator

from rddl_ide.core.statusbar import RunProgress, RunStopped, number

_ANSI_CODE = re.compile(r'\033\[[0-9;]*m')


def policy_from_code(source):
    '''Runs the source of a custom policy, which must define build_policy(env) and
    required_env_args(), and returns those two functions.'''
    namespace = {'__name__': '__policy__'}
    exec(compile(source, '<policy>', 'exec'), namespace)
    return namespace['build_policy'], namespace['required_env_args']


class _Episode:
    '''Reports each step of the episode, by wrapping the step() of the environment.'''

    def __init__(self, env, progress: RunProgress):
        self.steps, self.total, self.discount = 0, 0.0, 1.0
        env_step = env.step

        def step(action):
            result = env_step(action)
            reward = float(result[1])
            self.steps += 1
            self.total += reward * self.discount
            self.discount *= env.discount
            progress.step(self.steps, env.horizon, reward, self.total)
            return result
        env.step = step


def evaluate_policy(domain_file, inst_file, build_policy, required_env_args, viz, record,
                    progress: RunProgress):
    '''Runs one episode of the policy built by build_policy(env) in an environment made
    with the arguments returned by required_env_args(), showing its progress.'''
    env = None
    try:
        try:
            progress.note('Preparing the environment and the policy...')
            env_args = required_env_args()
            env = pyRDDLGym.make(domain=domain_file, instance=inst_file, **env_args)
            movie_gen = None
            if record is not None:
                movie_gen = MovieGenerator(record, env.model.domain_name, 9999)
            env.set_visualizer(viz, movie_gen=movie_gen)
            policy = progress.policy = build_policy(env)
            episode = _Episode(env, progress)
            policy.evaluate(env, episodes=1, verbose=True, render=True)
            env.close()
            env = None
            progress.finish(f'Done · {episode.steps} steps · return {number(episode.total)}')
            return None
        except Exception as error:
            print(traceback.format_exc(), file=sys.stderr)
            _close(env)
            env = None
            progress.finish('Stopped by an error')
            message = str(error)
            messagebox.showerror('pyRDDLGym error', _ANSI_CODE.sub('', message))
            return message
    except RunStopped:
        _close(env)
        return None


def _close(env) -> None:
    '''Closes the environment (and its visualizer) of a run that did not finish.'''
    if env is not None:
        try:
            env.close()
        except Exception:
            pass
