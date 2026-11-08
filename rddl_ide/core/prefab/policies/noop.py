from pyRDDLGym.core.policy import NoOpAgent

def build_policy(env):
    return NoOpAgent(action_space=env.action_space)

def required_env_args():
    return {}
