import math
import unittest

from rddl_ide.core.settings.introspect import MISSING
from rddl_ide.core.settings.model import (
    Field, FormState, Section, changed_values, format_value, parse_value
)


class TestValues(unittest.TestCase):

    def test_parse(self):
        self.assertEqual(parse_value('cvar'), 'cvar')
        self.assertEqual(parse_value("'cvar'"), 'cvar')
        self.assertEqual(parse_value('[1, 2]'), [1, 2])
        self.assertEqual(parse_value('None'), None)
        self.assertEqual(parse_value('inf'), math.inf)
        self.assertEqual(parse_value('-inf'), -math.inf)
        self.assertTrue(math.isnan(parse_value('nan')))
        self.assertEqual(parse_value('(0.0, inf)'), (0.0, math.inf))
        self.assertEqual(parse_value('(-inf, 1)'), (-math.inf, 1))
        self.assertEqual(parse_value('__import__("os")'), '__import__("os")')

    def test_format(self):
        self.assertEqual(format_value(0.5), '0.5')
        self.assertEqual(format_value('mean'), "'mean'")
        self.assertEqual(format_value(math.inf), 'inf')
        self.assertEqual(format_value(math.tanh), 'tanh')
        self.assertEqual(format_value(MISSING), '')
        self.assertEqual(format_value(lambda x: x), '<default>')

    def test_format_parse_round_trip(self):
        for value in (1, 0.25, 'adam', None, (1e-5, 1e5), {'a': [1]}, True, math.inf):
            self.assertEqual(parse_value(format_value(value)), value)


class TestChangedValues(unittest.TestCase):

    def setUp(self):
        self.fields = [
            Field('lr', 0.1),
            Field('flag', False),
            Field('needed'),
            Field('noise_kwargs', None, nested=[Field('eta'), Field('gamma'), Field('seed', None)]),
        ]
        self.section = Section('opt', '[Optimizer]', fields=lambda option, state: self.fields)
        self.state = FormState()

    def test_only_changed_values(self):
        self.state.set_text('opt', None, 'needed', '3')
        self.state.set_text('opt', None, 'lr', '0.1')  # equal to default
        self.state.set_text('opt', None, 'flag', 'True')
        self.assertEqual(changed_values(self.state, self.section, self.fields),
                         {'needed': 3, 'flag': True})

    def test_missing_required(self):
        with self.assertRaisesRegex(ValueError, 'needed'):
            changed_values(self.state, self.section, self.fields)

    def test_nested_required_only_when_used(self):
        self.state.set_text('opt', None, 'needed', '3')
        self.state.set_text('opt', None, 'noise_kwargs.gamma', '0.55')
        with self.assertRaisesRegex(ValueError, r'noise_kwargs\.eta'):
            changed_values(self.state, self.section, self.fields)
        self.state.set_text('opt', None, 'noise_kwargs.eta', '0.01')
        self.assertEqual(changed_values(self.state, self.section, self.fields)['noise_kwargs'],
                         {'eta': 0.01, 'gamma': 0.55})

    def test_extra_settings_merged(self):
        self.state.set_text('opt', None, 'needed', '3')
        self.state.set_extra('opt', "{'stopping_rule_kwargs': {'patience': 5}}")
        self.assertEqual(changed_values(self.state, self.section, self.fields)['stopping_rule_kwargs'],
                         {'patience': 5})

    def test_values_are_per_option(self):
        self.state.set_text('opt', 'a', 'lr', '0.5')
        self.assertIsNone(self.state.text('opt', 'b', 'lr'))
        self.assertEqual(self.state.text('opt', 'a', 'lr'), '0.5')


class TestRegistry(unittest.TestCase):

    def test_detect_kind(self):
        from rddl_ide.core.settings.registry import detect_kind
        self.assertEqual(detect_kind('# rddl-ide: jaxplan-online\n[Planner]\n'), 'jaxplan-online')
        self.assertEqual(detect_kind("[Compiler]\n[Planner]\nmethod='x'\n[Optimize]\n"),
                         'jaxplan-offline')
        self.assertEqual(detect_kind('[Gurobi]\n[Optimizer]\n'), 'gurobi-online')
        self.assertEqual(detect_kind("[Agent]\nagent='RandomAgent'\n"), 'builtin')
        self.assertIsNone(detect_kind('[Something]\n'))


if __name__ == '__main__':
    unittest.main()
