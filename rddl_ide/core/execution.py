import re
import sys
import traceback
from tkinter import messagebox

import pyRDDLGym
from pyRDDLGym.core.visualizer.movie import MovieGenerator

_ANSI_CODE = re.compile(r'\033\[[0-9;]*m')


def _handle_error_message(err):

    syntax_error = re.search(r'\033\[4m(.*?)\033\[(?:24|0)m', err)
    if syntax_error is not None:  # syntax error: the underlined line
        err = syntax_error.group(1).strip()
    
    elif '>>' in err:  # compiler error in general
        start = err.index('>>') + len('>>')
        err = _ANSI_CODE.sub('', err[start:])
        if 'Please check expression' in err:
            end = err.index('Please check expression')
            err = err[:end]
        err = err.strip()
    
    else:  # do not highlight
        err = None
    
    return err
    
    
def policy_from_code(source):
    '''Runs the source of a custom policy, which must define build_policy(env) and
    required_env_args(), and returns those two functions.'''
    namespace = {'__name__': '__policy__'}
    exec(compile(source, '<policy>', 'exec'), namespace)
    return namespace['build_policy'], namespace['required_env_args']


def evaluate_policy(domain_file, inst_file, build_policy, required_env_args, viz, record):
    '''Runs one episode of the policy built by build_policy(env) in an environment made
    with the arguments returned by required_env_args(); shows an error in a dialog and
    returns the part of the domain to highlight for it, if any.'''

    def target():
        try:
            env_args = required_env_args()
            env = pyRDDLGym.make(domain=domain_file, instance=inst_file, **env_args)
            movie_gen = None
            if record is not None:
                movie_gen = MovieGenerator(record, env.model.domain_name, 9999)
            env.set_visualizer(viz, movie_gen=movie_gen)
            policy = build_policy(env) 
            policy.evaluate(env, episodes=1, verbose=True, render=True)
            env.close()
            return None
        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            return e
    
    err = target()
    if err is None:
        return None
    err = str(err)
    messagebox.showerror('pyRDDLGym error', _ANSI_CODE.sub('', err))
    return _handle_error_message(err)

