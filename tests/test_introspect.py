import unittest

from rddl_ide.core.settings.introspect import (
    MISSING, concrete_subclasses, signature_fields, trace_kwargs_target
)

try:
    import optax
    from pyRDDLGym_jax.core import logic, plan, planner
except ImportError:
    planner = None


class Base:
    def __init__(self, a, b=1, *args, **kwargs):
        pass


class Child(Base):
    def __init__(self, c=2.0, b=5, **kwargs):
        super().__init__(**kwargs)


def function(x, y='s', *, z=None):
    pass


class TestSignatureFields(unittest.TestCase):

    def test_class_walks_mro_and_first_default_wins(self):
        fields = {f.name: f.default for f in signature_fields(Child)}
        self.assertEqual(fields, {'c': 2.0, 'b': 5, 'a': MISSING})

    def test_function_and_exclusions(self):
        fields = [f.name for f in signature_fields(function, exclude={'x'})]
        self.assertEqual(fields, ['y', 'z'])

    def test_required_flag(self):
        fields = {f.name: f.required for f in signature_fields(Base)}
        self.assertEqual(fields, {'a': True, 'b': False})

    def test_concrete_subclasses(self):
        import types
        module = types.ModuleType('m')
        module.Base, module.Child = Base, Child
        Base.__module__ = Child.__module__ = 'm'
        self.assertEqual(list(concrete_subclasses(module, Base)), ['Child'])


@unittest.skipIf(planner is None, 'pyRDDLGym-jax is not installed')
class TestJaxPlan(unittest.TestCase):

    def test_inherited_compiler_settings(self):
        names = [f.name for f in signature_fields(logic.DefaultJaxRDDLCompilerWithGrad)]
        self.assertGreaterEqual(len(names), 30)
        self.assertIn('sigmoid_weight', names)

    def test_trace_kwargs(self):
        self.assertIs(trace_kwargs_target([planner, plan], 'noise_kwargs'), optax.add_noise)
        self.assertIs(trace_kwargs_target([planner, plan], 'line_search_kwargs'),
                      optax.scale_by_zoom_linesearch)
        self.assertIsNone(trace_kwargs_target([planner, plan], 'utility_kwargs'))


if __name__ == '__main__':
    unittest.main()
