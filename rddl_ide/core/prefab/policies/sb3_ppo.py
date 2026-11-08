from pyRDDLGym_rl.core.env import SimplifiedActionRDDLEnv
from pyRDDLGym_rl.core.sb3_trainer import StableBaselinesTrainer

def build_policy(env):
    trainer = StableBaselinesTrainer(env, 'ppo')
    trainer.train(total_timesteps=200000)
    return trainer.agent()

def required_env_args():
    return {'base_class': SimplifiedActionRDDLEnv, 'action_mode': 'auto'}
