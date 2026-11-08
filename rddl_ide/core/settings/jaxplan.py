'''JaxPlan (pyRDDLGym-jax) as a settings form, read from the installed package.'''
import functools
import inspect
import os
from typing import Any, Dict, List, Optional

import optax
import pyRDDLGym_jax
from pyRDDLGym_jax.core import config, controller, logic, plan, planner

from rddl_ide.core.settings.introspect import concrete_subclasses, signature_fields
from rddl_ide.core.settings.model import Field, FormState, Section
from rddl_ide.core.settings.provider import (
    Provider, assign, fields_with_traced_kwargs, read_config, write_config
)

# arguments a config cannot set: objects that the config loader or the planner supply
NOT_CONFIGURABLE_COMPILER = {'rddl', 'logger', 'python_functions'}
NOT_CONFIGURABLE_PLANNER = {'rddl', 'plan', 'compiler', 'compiler_kwargs', 'logger',
                            'dashboard_viz', 'python_functions', 'critic'}
NOT_CONFIGURABLE_OPTIMIZE = {'subs', 'guess', 'model_params', 'critic_params',
                             'dashboard_id', 'tqdm_position', 'planner'}

# settings of the planner shown in sections of their own
PLANNER_CHOICES = {'auxiliary', 'optimizer', 'optimizer_kwargs'}

TRACE_MODULES = (planner, plan, logic)


@functools.lru_cache(maxsize=None)
def optax_optimizers() -> List[str]:
    '''Every public optax function that takes a learning rate and returns a gradient
    transformation, i.e. the optimizers a config can name.'''
    names = []
    for (name, obj) in vars(optax).items():
        if name.startswith('_') or not inspect.isfunction(obj):
            continue
        try:
            signature = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        if 'learning_rate' in signature.parameters and \
                'GradientTransformation' in str(signature.return_annotation):
            names.append(name)
    return sorted(names)


def _default_of(obj, name: str) -> Any:
    for field in signature_fields(obj):
        if field.name == name:
            return field.default
    return None


class JaxPlanProvider(Provider):

    def __init__(self, online: bool) -> None:
        self.online = online
        self.kind = 'jaxplan-online' if online else 'jaxplan-offline'
        self.title = 'JaxPlan (online)' if online else 'JaxPlan (offline)'
        self.controller = controller.JaxOnlineController if online \
            else controller.JaxOfflineController
        self.planners = concrete_subclasses(planner, planner.JaxPlanner)
        self.plans = concrete_subclasses(plan, plan.JaxPlan)
        self.compilers = {name: obj for (name, obj) in vars(logic).items()
                          if isinstance(obj, type) and obj.__module__ == logic.__name__
                          and issubclass(obj, logic.JaxRDDLCompilerWithGrad)
                          and 'Compiler' in name}
        self.base_planner_args = set(inspect.signature(planner.JaxPlanner.__init__).parameters)
        self._sections = self._make_sections()

    # ===========================================================================
    # sections
    # ===========================================================================

    def _planner_class(self, state: FormState) -> type:
        return self.planners[self._planner_section.option(state)]

    def _planner_scope(self, state: FormState) -> str:
        return self._planner_section.option(state) or ''

    @functools.lru_cache(maxsize=None)
    def _compiler_fields(self, option: str) -> List[Field]:
        return fields_with_traced_kwargs(
            self.compilers[option], TRACE_MODULES, NOT_CONFIGURABLE_COMPILER)

    @functools.lru_cache(maxsize=None)
    def _planner_fields(self, option: str) -> List[Field]:
        return fields_with_traced_kwargs(
            self.planners[option], TRACE_MODULES, NOT_CONFIGURABLE_PLANNER | PLANNER_CHOICES)

    @functools.lru_cache(maxsize=None)
    def _auxiliary_fields(self, option: str) -> List[Field]:
        if option not in self.planners:
            return []

        # an auxiliary planner ignores the arguments it shares with the planner it runs
        # alongside, so only the arguments its class adds are settings
        return fields_with_traced_kwargs(
            self.planners[option], TRACE_MODULES,
            NOT_CONFIGURABLE_PLANNER | self.base_planner_args)

    @functools.lru_cache(maxsize=None)
    def _plan_fields(self, option: str) -> List[Field]:
        return fields_with_traced_kwargs(self.plans[option], TRACE_MODULES)

    @functools.lru_cache(maxsize=None)
    def _optimizer_fields(self, option: str, planner_option: str) -> List[Field]:
        has_kwargs = any(f.name == 'optimizer_kwargs'
                         for f in signature_fields(self.planners[planner_option]))
        if not has_kwargs or not hasattr(optax, option):
            return []
        return signature_fields(getattr(optax, option))

    @functools.lru_cache(maxsize=None)
    def _optimize_fields(self) -> List[Field]:
        fields = signature_fields(planner.JaxPlanner.optimize_generator, NOT_CONFIGURABLE_OPTIMIZE)
        names = {field.name for field in fields}
        fields += [field for field in signature_fields(self.controller, NOT_CONFIGURABLE_OPTIMIZE)
                   if field.name not in names]
        return fields

    def _default_auxiliary(self, state: FormState) -> str:
        default = _default_of(self._planner_class(state), 'auxiliary')
        return type(default).__name__ if isinstance(default, planner.JaxPlanner) else 'None'

    def _default_optimizer(self, state: FormState) -> Optional[str]:
        default = _default_of(self._planner_class(state), 'optimizer')
        return getattr(default, '__name__', default)

    def _has_optimizer(self, state: FormState) -> bool:
        return any(f.name == 'optimizer' for f in signature_fields(self._planner_class(state)))

    def _make_sections(self) -> List[Section]:
        default_compiler = _default_of(planner.JaxPlanner, 'compiler')
        compiler = Section(
            'compiler', '[Compiler]', chooser='method',
            fields=lambda option, state: self._compiler_fields(option),
            options=lambda state: sorted(self.compilers),
            default_option=lambda state: getattr(default_compiler, '__name__', None))
        self._planner_section = planners = Section(
            'planner', '[Planner]', chooser='planner',
            fields=lambda option, state: self._planner_fields(option),
            options=lambda state: sorted(self.planners),
            default_option=lambda state: 'JaxBackpropPlanner')
        auxiliary = Section(
            'auxiliary', '[Planner] auxiliary planner', chooser='auxiliary',
            fields=lambda option, state: self._auxiliary_fields(option),
            options=lambda state: ['None'] + sorted(self.planners),
            default_option=self._default_auxiliary, scope=self._planner_scope)
        plans = Section(
            'plan', '[Planner] method (plan or policy)', chooser='method',
            fields=lambda option, state: self._plan_fields(option),
            options=lambda state: sorted(self.plans),
            default_option=lambda state: 'JaxStraightLinePlan')
        optimizer = Section(
            'optimizer', '[Planner] optimizer', chooser='optimizer',
            fields=lambda option, state: self._optimizer_fields(option, planners.option(state)),
            options=lambda state: optax_optimizers(),
            default_option=self._default_optimizer, scope=self._planner_scope,
            visible=self._has_optimizer, required_when_used=True)
        optimize = Section(
            'optimize', '[Optimize]', fields=lambda option, state: self._optimize_fields())
        return [planners, compiler, auxiliary, plans, optimizer, optimize]

    def sections(self) -> List[Section]:
        return self._sections

    # ===========================================================================
    # configs
    # ===========================================================================

    def initial_state(self) -> FormState:
        name = 'default_replan.cfg' if self.online else 'default_slp.cfg'
        path = os.path.join(os.path.dirname(pyRDDLGym_jax.__file__), 'examples', 'configs', name)
        if os.path.isfile(path):
            with open(path) as file:
                return self.from_config(file.read())
        return FormState()

    def to_config(self, state: FormState) -> str:
        compiler, planners, auxiliary, plans, optimizer = (
            self.section(name) for name in ('compiler', 'planner', 'auxiliary', 'plan', 'optimizer'))
        compiler_values = {'method': compiler.option(state), **self.changed(state, 'compiler')}

        planner_values = {'planner': planners.option(state), 'method': plans.option(state)}
        plan_kwargs = self.changed(state, 'plan')
        if plan_kwargs:
            planner_values['method_kwargs'] = plan_kwargs
        if optimizer.visible(state):
            optimizer_kwargs = self.changed(state, 'optimizer')
            if optimizer.option(state) != self._default_optimizer(state) or optimizer_kwargs:
                planner_values['optimizer'] = optimizer.option(state)
            if optimizer_kwargs:
                planner_values['optimizer_kwargs'] = optimizer_kwargs
        auxiliary_option = auxiliary.option(state)
        auxiliary_kwargs = self.changed(state, 'auxiliary')
        if auxiliary_option != self._default_auxiliary(state) or auxiliary_kwargs:
            planner_values['auxiliary'] = None if auxiliary_option == 'None' else auxiliary_option
        if auxiliary_kwargs:
            planner_values['auxiliary_kwargs'] = auxiliary_kwargs
        planner_values.update(self.changed(state, 'planner'))

        return write_config(self.kind, [('Compiler', compiler_values),
                                        ('Planner', planner_values),
                                        ('Optimize', self.changed(state, 'optimize'))])

    def from_config(self, text: str) -> FormState:
        values = read_config(text)
        state = FormState()
        compiler_values = dict(values.get('Compiler', {}))
        planner_values = dict(values.get('Planner', {}))

        # choices first, since the other sections' fields depend on them
        for (section_id, values_of, key) in [('planner', planner_values, 'planner'),
                                             ('compiler', compiler_values, 'method'),
                                             ('plan', planner_values, 'method'),
                                             ('optimizer', planner_values, 'optimizer'),
                                             ('auxiliary', planner_values, 'auxiliary')]:
            if key in values_of:
                option = values_of.pop(key)
                option = 'None' if option is None else str(option)
                self.section(section_id).choose(state, option)
        def pop_dict(key):  # a value that is not a dict stays with the planner settings
            value = planner_values.get(key)
            if value is None or isinstance(value, dict):
                planner_values.pop(key, None)
                return value or {}
            return {}

        assign(state, self.section('compiler'), compiler_values)
        assign(state, self.section('plan'), pop_dict('method_kwargs'))
        assign(state, self.section('optimizer'), pop_dict('optimizer_kwargs'))
        assign(state, self.section('auxiliary'), pop_dict('auxiliary_kwargs'))
        assign(state, self.section('planner'), planner_values)
        assign(state, self.section('optimize'), values.get('Optimize', {}))
        return state

    # ===========================================================================
    # running
    # ===========================================================================

    def env_args(self, state: FormState) -> Dict[str, Any]:
        return {'vectorized': True}

    def build_policy(self, env, state: FormState):
        planner_args, _, train_args = config.load_config_from_string(self.to_config(state))
        if 'dashboard' in planner_args:
            planner_args['dashboard'].launch()
        jax_planner = planner.create_planner(
            rddl=env.model, dashboard_viz=getattr(env, '_visualizer', None), **planner_args)
        return self.controller(jax_planner, **train_args)
