from pyRDDLGym.core.policy import RandomAgent

def build_policy(env):
    return RandomAgent(env)

def required_env_args():
    return {}
