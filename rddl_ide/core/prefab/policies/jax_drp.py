from pyRDDLGym_jax.core.planner import (
    load_config_from_string, JaxBackpropPlanner, JaxOfflineController
)     

PARAMETERS = """
    [Compiler]
    method='DefaultJaxRDDLCompilerWithGrad'
    
    [Planner]
    method='JaxDeepReactivePolicy'
    method_kwargs={'topology': [128, 64], 'activation': 'tanh'}
    optimizer='rmsprop'
    optimizer_kwargs={'learning_rate': 0.001}
    batch_size_train=32
    batch_size_test=32
    
    [Optimize]
    key=42
    epochs=30000
    train_seconds=60
    policy_hyperparams=2.0
"""

def build_policy(env):
    planner_args, _, train_args = load_config_from_string(PARAMETERS)
    planner = JaxBackpropPlanner(rddl=env.model, **planner_args)
    return JaxOfflineController(planner, **train_args)

def required_env_args():
    return {'vectorized': True}