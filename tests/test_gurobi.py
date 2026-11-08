import math
import os
import unittest
import warnings

try:
    import gurobipy
    import pyRDDLGym_gurobi
    from pyRDDLGym_gurobi.core import planner as gurobi_planner
except ImportError:
    gurobipy = None
else:
    from rddl_ide.core.settings.gurobi import GurobiProvider

from rddl_ide.core.settings.model import FormState
from rddl_ide.core.settings.provider import config_kind, read_config


@unittest.skipIf(gurobipy is None, 'gurobipy or pyRDDLGym-gurobi is not installed')
class TestGurobiProvider(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings('ignore')
        self.provider = GurobiProvider()
        self.state = FormState()

    def fields(self, section_id):
        section = self.provider.section(section_id)
        return {f.name: f for f in section.fields(section.option(self.state), self.state)}

    def test_solver_parameters_need_no_license(self):
        fields = self.fields('gurobi')
        self.assertGreaterEqual(len(fields), 200)
        self.assertEqual(fields['TimeLimit'].default, math.inf)
        self.assertEqual(fields['NonConvex'].default, -1)

    def test_plans_and_compiler_settings(self):
        plan = self.provider.section('plan')
        self.assertIn('GurobiStraightLinePlan', plan.options(self.state))
        self.assertIn('GurobiPiecewisePolicy', plan.options(self.state))
        fields = self.fields('optimizer')
        self.assertIn('rollout_horizon', fields)
        self.assertNotIn('rddl', fields)

    def test_infinity_written_for_the_loader(self):
        self.state.set_text('gurobi', None, 'TimeLimit', '60')
        self.state.set_text('gurobi', None, 'MIPGap', 'inf')
        text = self.provider.to_config(self.state)
        args = gurobi_planner.load_config_from_string(text)
        self.assertEqual(args['model_params'], {'TimeLimit': 60, 'MIPGap': math.inf})

    def test_example_config_round_trip(self):
        path = os.path.join(os.path.dirname(pyRDDLGym_gurobi.__file__), 'examples', 'default.cfg')
        with open(path) as file:
            first = self.provider.to_config(self.provider.from_config(file.read()))
        self.assertEqual(config_kind(first), 'gurobi-online')
        self.assertEqual(self.provider.to_config(self.provider.from_config(first)), first)
        values = read_config(first)
        self.assertEqual(values['Gurobi']['NonConvex'], 2)
        self.assertEqual(values['Optimizer']['rollout_horizon'], 5)

    def test_online_run(self):
        import pyRDDLGym
        env = pyRDDLGym.make('Reservoir_Continuous', '1', **self.provider.env_args(self.state))
        state = self.provider.initial_state()
        state.set_text('optimizer', None, 'rollout_horizon', '2')
        state.set_text('gurobi', None, 'OutputFlag', '0')
        policy = self.provider.build_policy(env, state)
        policy.reset()
        state0, _ = env.reset()
        action = policy.sample_action(state0)
        self.assertIsInstance(action, dict)
        env.close()


if __name__ == '__main__':
    unittest.main()
