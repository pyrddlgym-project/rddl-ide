from pyRDDLGym_jax.core.planner import (
     load_config_from_string, JaxBackpropPlanner, JaxOnlineController
)
     
PARAMETERS = """
    [Compiler]

    [Planner]
    method='JaxStraightLinePlan'
    method_kwargs={}
    optimizer='rmsprop'
    optimizer_kwargs={'learning_rate': 0.01}
    batch_size_train=32
    batch_size_test=32
    rollout_horizon=5
    
    [Optimize]
    key=42
    epochs=5000
    train_seconds=2
    policy_hyperparams=2.0
"""

def build_policy(env):
    planner_args, _, train_args = load_config_from_string(PARAMETERS)    
    planner = JaxBackpropPlanner(rddl=env.model, **planner_args)
    return JaxOnlineController(planner, **train_args)

def required_env_args():
    return {'vectorized': True}