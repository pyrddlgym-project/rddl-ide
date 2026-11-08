from pyRDDLGym_jax.core.config import load_config_from_string
from pyRDDLGym_jax.core.controller import JaxOnlineController
from pyRDDLGym_jax.core.planner import create_planner

PARAMETERS = """
    [Compiler]
    method='DefaultJaxRDDLCompilerWithGrad'

    [Planner]
    planner='JaxLMMAESPlanner'
    method='JaxStraightLinePlan'
    method_kwargs={}
    batch_size_train=32
    batch_size_test=32
    rollout_horizon=5
    auxiliary=None

    [Optimize]
    key=42
    epochs=2000
    train_seconds=2
    print_summary=False
"""

def build_policy(env):
    planner_args, _, train_args = load_config_from_string(PARAMETERS)
    planner = create_planner(rddl=env.model, **planner_args)
    return JaxOnlineController(planner, **train_args)

def required_env_args():
    return {'vectorized': True}
