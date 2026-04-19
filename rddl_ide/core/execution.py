import sys
import traceback
from tkinter import messagebox

import pyRDDLGym
from pyRDDLGym.core.visualizer.movie import MovieGenerator


def _handle_error_message(err):
    
    if '\033[4m' in err and '\033[0m' in err:  # syntax error
        start = err.index('\033[4m') + len('\033[4m')
        end = err.index('\033[0m')
        err = err[start:end].strip()
    
    elif '>>' in err:  # compiler error in general
        start = err.index('>>') + len('>>')
        err = err[start:]    
        if 'Please check expression' in err:
            end = err.index('Please check expression')
            err = err[:end]
        err = err.strip()
    
    else:  # do not highlight
        err = None
    
    return err
    
    
def evaluate_policy_fn(domain_file, inst_file, policy_editor, viz, record):
    
    # compile policy from given class
    policy_source = policy_editor.get(1.0, 'end')
    try:
        compiled = compile(policy_source, '', 'exec')
        exec(compiled, globals())
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        messagebox.showerror('Python error', e)
        
    # evaluation handle
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
    if err is not None:
        messagebox.showerror('pyRDDLGym error', err)
    return _handle_error_message(str(err))

