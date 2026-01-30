from pyRDDLGym.core.policy import RandomAgent

def build_policy(env):
    return RandomAgent(action_space=env.action_space, num_actions=env.max_allowed_actions)

def required_env_args():
    return {}