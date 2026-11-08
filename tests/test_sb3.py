import unittest
import warnings

try:
    import stable_baselines3
    import pyRDDLGym_rl
except ImportError:
    stable_baselines3 = None
else:
    from rddl_ide.core.settings.sb3 import StableBaselinesProvider

from rddl_ide.core.settings.model import FormState
from rddl_ide.core.settings.provider import config_kind, read_config


@unittest.skipIf(stable_baselines3 is None, 'stable-baselines3 or pyRDDLGym-rl is not installed')
class TestStableBaselinesProvider(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings('ignore')
        self.provider = StableBaselinesProvider()
        self.state = FormState()

    def fields(self, section_id):
        section = self.provider.section(section_id)
        return {f.name: f for f in section.fields(section.option(self.state), self.state)}

    def test_algorithms_and_settings(self):
        algorithm = self.provider.section('algorithm')
        self.assertIn('ppo', algorithm.options(self.state))
        self.assertEqual(algorithm.option(self.state), 'ppo')
        self.assertIn('n_steps', self.fields('algorithm'))
        self.assertNotIn('env', self.fields('algorithm'))
        self.assertTrue(self.fields('train')['total_timesteps'].required)
        self.assertIn('action_mode', self.fields('environment'))

    def test_round_trip(self):
        self.provider.section('algorithm').choose(self.state, 'dqn')
        self.state.set_text('train', None, 'total_timesteps', '1000')
        self.state.set_text('environment', None, 'action_mode', 'discrete')
        text = self.provider.to_config(self.state)
        self.assertEqual(config_kind(text), 'sb3')
        self.assertEqual(read_config(text)['Algorithm'], {'method': 'dqn'})
        self.assertEqual(self.provider.to_config(self.provider.from_config(text)), text)

    def test_short_training_run(self):
        import pyRDDLGym
        self.state.set_text('train', None, 'total_timesteps', '256')
        self.state.set_text('algorithm', 'ppo', 'n_steps', '64')
        self.state.set_text('environment', None, 'action_mode', 'auto')
        env = pyRDDLGym.make('Wildfire_MDP_ippc2014', '1', **self.provider.env_args(self.state))
        result = self.provider.build_policy(env, self.state).evaluate(env, episodes=1)
        self.assertIn('mean', result)
        env.close()


if __name__ == '__main__':
    unittest.main()
