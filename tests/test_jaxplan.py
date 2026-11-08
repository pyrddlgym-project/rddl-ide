import os
import unittest
import warnings

try:
    from pyRDDLGym_jax.core import config as jax_config, planner as jax_planner
except ImportError:
    jax_config = None
else:
    from rddl_ide.core.settings.jaxplan import JaxPlanProvider

from rddl_ide.core.settings.model import FormState
from rddl_ide.core.settings.provider import config_kind, read_config


@unittest.skipIf(jax_config is None, 'pyRDDLGym-jax is not installed')
class TestJaxPlanProvider(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings('ignore')
        self.provider = JaxPlanProvider(online=False)
        self.state = FormState()

    def choose(self, section_id, option):
        self.provider.section(section_id).choose(self.state, option)

    def fields(self, section_id):
        section = self.provider.section(section_id)
        return {f.name: f for f in section.fields(section.option(self.state), self.state)}

    def test_every_planner_and_plan_gives_a_loadable_config(self):
        planners = self.provider.section('planner').options(self.state)
        plans = self.provider.section('plan').options(self.state)
        self.assertIn('JaxBackpropPlanner', planners)
        self.assertIn('JaxStraightLinePlan', plans)
        for planner_name in planners:
            for plan_name in plans:
                state = FormState()
                self.provider.section('planner').choose(state, planner_name)
                self.provider.section('plan').choose(state, plan_name)
                text = self.provider.to_config(state)
                jax_config.load_config_from_string(text)

    def test_planner_settings_redraw(self):
        self.choose('planner', 'JaxLMMAESPlanner')
        lmmaes = set(self.fields('planner'))
        self.choose('planner', 'JaxPGPEPlanner')
        pgpe = set(self.fields('planner'))
        self.assertIn('population_size', lmmaes - pgpe)
        self.assertIn('super_symmetric', pgpe - lmmaes)
        self.assertIn('batch_size_train', lmmaes & pgpe)

    def test_default_auxiliary(self):
        aux = self.provider.section('auxiliary')
        self.assertEqual(aux.option(self.state), 'JaxLMMAESPlanner')
        self.assertIn('population_size', self.fields('auxiliary'))
        self.assertNotIn('batch_size_train', self.fields('auxiliary'))
        self.choose('planner', 'JaxPGPEPlanner')
        self.assertEqual(aux.option(self.state), 'None')

    def test_auxiliary_edit_writes_class_and_kwargs(self):
        self.state.set_text('auxiliary', 'JaxLMMAESPlanner', 'population_size', '64')
        values = read_config(self.provider.to_config(self.state))['Planner']
        self.assertEqual(values['auxiliary'], 'JaxLMMAESPlanner')
        self.assertEqual(values['auxiliary_kwargs'], {'population_size': 64})
        self.choose('auxiliary', 'None')
        values = read_config(self.provider.to_config(self.state))['Planner']
        self.assertIsNone(values['auxiliary'])
        self.assertNotIn('auxiliary_kwargs', values)

    def test_switching_planner_keeps_edits_and_auxiliary_default(self):
        self.state.set_text('planner', 'JaxBackpropPlanner', 'batch_size_train', '7')
        self.choose('auxiliary', 'None')
        self.choose('planner', 'JaxPGPEPlanner')
        self.choose('planner', 'JaxBackpropPlanner')
        self.assertEqual(self.provider.changed(self.state, 'planner')['batch_size_train'], 7)
        self.assertEqual(self.provider.section('auxiliary').option(self.state), 'None')

    def test_optimizer_choices_come_from_optax(self):
        optimizer = self.provider.section('optimizer')
        options = optimizer.options(self.state)
        self.assertGreaterEqual(len(options), 20)
        self.assertIn('adam', options)
        self.assertEqual(optimizer.option(self.state), 'rmsprop')
        self.choose('optimizer', 'adam')
        self.assertIn('b1', self.fields('optimizer'))
        self.state.set_text('optimizer', 'adam', 'learning_rate', '0.003')
        values = read_config(self.provider.to_config(self.state))['Planner']
        self.assertEqual(values['optimizer'], 'adam')
        self.assertEqual(values['optimizer_kwargs'], {'learning_rate': 0.003})

    def test_traced_and_untraced_kwargs(self):
        fields = self.fields('planner')
        self.assertEqual([f.name for f in fields['noise_kwargs'].nested][:2], ['eta', 'gamma'])
        self.assertIsNone(fields['utility_kwargs'].nested)

    def test_nested_required_value(self):
        self.state.set_text('planner', 'JaxBackpropPlanner', 'noise_kwargs.gamma', '0.55')
        with self.assertRaisesRegex(ValueError, r'noise_kwargs\.eta'):
            self.provider.to_config(self.state)

    def test_unquoted_string_value(self):
        self.state.set_text('planner', 'JaxBackpropPlanner', 'utility', 'cvar')
        self.state.set_text('planner', 'JaxBackpropPlanner', 'utility_kwargs', "{'alpha': 0.1}")
        values = read_config(self.provider.to_config(self.state))['Planner']
        self.assertEqual(values['utility'], 'cvar')
        self.assertEqual(values['utility_kwargs'], {'alpha': 0.1})

    def test_config_round_trip(self):
        configs = os.path.join(os.path.dirname(jax_planner.__file__), '..', 'examples', 'configs')
        for name in sorted(os.listdir(configs)):
            if not name.endswith('.cfg') or name.startswith('tuning'):  # templates
                continue
            with open(os.path.join(configs, name)) as file:
                text = file.read()
            first = self.provider.to_config(self.provider.from_config(text))
            second = self.provider.to_config(self.provider.from_config(first))
            self.assertEqual(first, second, name)
            jax_config.load_config_from_string(first)
            self.assertEqual(config_kind(first), 'jaxplan-offline')

    def test_unknown_keys_survive_round_trip(self):
        text = ("[Compiler]\n[Planner]\nmethod='JaxStraightLinePlan'\n"
                "[Optimize]\nstopping_rule='NoImprovementStoppingRule'\n"
                "stopping_rule_kwargs={'patience': 5}\n")
        values = read_config(self.provider.to_config(self.provider.from_config(text)))
        self.assertEqual(values['Optimize']['stopping_rule_kwargs'], {'patience': 5})
        self.assertEqual(values['Optimize']['stopping_rule'], 'NoImprovementStoppingRule')

    def test_initial_states_load(self):
        for online in (False, True):
            provider = JaxPlanProvider(online=online)
            text = provider.to_config(provider.initial_state())
            jax_config.load_config_from_string(text)
        online = read_config(JaxPlanProvider(online=True).to_config(
            JaxPlanProvider(online=True).initial_state()))
        self.assertEqual(online['Planner']['planner'], 'JaxLMMAESPlanner')

    def test_offline_run(self):
        import pyRDDLGym
        env = pyRDDLGym.make('Reservoir_Continuous', '1',
                             **self.provider.env_args(self.state))
        state = self.provider.initial_state()
        state.set_text('optimize', None, 'train_seconds', '2')
        state.set_text('optimize', None, 'epochs', '200')
        policy = self.provider.build_policy(env, state)
        result = policy.evaluate(env, episodes=1)
        self.assertIn('mean', result)
        env.close()


if __name__ == '__main__':
    unittest.main()
