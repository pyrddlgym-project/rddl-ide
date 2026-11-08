from pyRDDLGym_jax.core.config import load_config_from_string
from pyRDDLGym_jax.core.controller import JaxOfflineController
from pyRDDLGym_jax.core.planner import create_planner

PARAMETERS = """
    [Compiler]
    method='DefaultJaxRDDLCompilerWithGrad'

    [Planner]
    method='JaxStraightLinePlan'
    method_kwargs={}
    optimizer='rmsprop'
    optimizer_kwargs={'learning_rate': 0.01}
    batch_size_train=32
    batch_size_test=32

    [Optimize]
    key=42
    epochs=30000
    train_seconds=60
"""

def build_policy(env):
    planner_args, _, train_args = load_config_from_string(PARAMETERS)
    planner = create_planner(rddl=env.model, **planner_args)
    return JaxOfflineController(planner, **train_args)

def required_env_args():
    return {'vectorized': True}
