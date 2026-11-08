import unittest
import warnings

import pyRDDLGym

from rddl_ide.core.settings.builtin import BuiltinAgentProvider
from rddl_ide.core.settings.model import FormState
from rddl_ide.core.settings.provider import config_kind, read_config


class TestBuiltinAgentProvider(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings('ignore')
        self.provider = BuiltinAgentProvider()
        self.state = FormState()
        self.agent = self.provider.section('agent')

    def fields(self):
        option = self.agent.option(self.state)
        return {f.name: f for f in self.agent.fields(option, self.state)}

    def test_agents_found(self):
        options = self.agent.options(self.state)
        for name in ('NoOpAgent', 'RandomAgent', 'RolloutAgent', 'RandomShootingAgent'):
            self.assertIn(name, options)
        self.assertEqual(self.agent.option(self.state), 'NoOpAgent')

    def test_env_supplied_arguments_hidden(self):
        self.agent.choose(self.state, 'RandomAgent')
        self.assertNotIn('env', self.fields())
        self.assertIn('seed', self.fields())

    def test_required_argument(self):
        self.agent.choose(self.state, 'RolloutAgent')
        self.assertTrue(self.fields()['num_candidates'].required)
        env = pyRDDLGym.make('Wildfire_MDP_ippc2014', '1')
        with self.assertRaisesRegex(ValueError, 'num_candidates'):
            self.provider.build_policy(env, self.state)
        env.close()

    def test_round_trip(self):
        self.agent.choose(self.state, 'RandomAgent')
        self.state.set_text('agent', 'RandomAgent', 'seed', '42')
        text = self.provider.to_config(self.state)
        self.assertEqual(config_kind(text), 'builtin')
        self.assertEqual(read_config(text)['Agent'], {'agent': 'RandomAgent', 'seed': 42})
        self.assertEqual(self.provider.to_config(self.provider.from_config(text)), text)

    def test_random_run(self):
        self.agent.choose(self.state, 'RandomAgent')
        self.state.set_text('agent', 'RandomAgent', 'seed', '1')
        env = pyRDDLGym.make('Wildfire_MDP_ippc2014', '1', **self.provider.env_args(self.state))
        result = self.provider.build_policy(env, self.state).evaluate(env, episodes=1)
        self.assertIn('mean', result)
        env.close()


if __name__ == '__main__':
    unittest.main()
