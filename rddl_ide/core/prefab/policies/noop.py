from pyRDDLGym.core.policy import NoOpAgent

def build_policy(env):
    return NoOpAgent(action_space=env.action_space, num_actions=env.max_allowed_actions)
    
def required_env_args():
    return {}