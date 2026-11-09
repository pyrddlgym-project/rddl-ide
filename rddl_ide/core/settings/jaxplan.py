'''JaxPlan (pyRDDLGym-jax) as a settings form, read from the installed package.'''
import dataclasses
import functools
import inspect
import os
import pickle
from typing import Any, Dict, List, Optional

import numpy as np
import optax
import pyRDDLGym_jax
from pyRDDLGym_jax.core import config, controller, logic, plan, planner

from rddl_ide.core.settings.introspect import concrete_subclasses, signature_fields
from rddl_ide.core.settings.model import Field, FormState, Section, format_value
from rddl_ide.core.settings.provider import (
    Provider, assign, fields_with_traced_kwargs, read_config, write_config
)
from rddl_ide.core.statusbar import number

# arguments a config cannot set: objects that the config loader or the planner supply
NOT_CONFIGURABLE_COMPILER = {'rddl', 'logger', 'python_functions'}
NOT_CONFIGURABLE_PLANNER = {'rddl', 'plan', 'compiler', 'compiler_kwargs', 'logger',
                            'dashboard_viz', 'python_functions', 'critic'}
NOT_CONFIGURABLE_OPTIMIZE = {'subs', 'guess', 'model_params', 'critic_params',
                             'dashboard_id', 'tqdm_position', 'planner'}

# the trained weights of an offline controller, as its save_path setting writes them
WEIGHT_FILES = [('JaxPlan weights', '*.pickle *.pkl'), ('All files', '*.*')]

# settings of the planner shown in sections of their own
PLANNER_CHOICES = {'auxiliary'}

# arguments that the config loader resolves from a name to an optax optimizer
OPTIMIZER_ARGS = ('optimizer', 'optimizer_sigma')
OPTIMIZER_KWARGS = 'optimizer_kwargs'

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


@functools.lru_cache(maxsize=None)
def _optax_fields(name: str) -> List[Field]:
    return signature_fields(getattr(optax, name))


def with_optimizer_choices(fields: List[Field], section_id: str, option: Optional[str],
                           state: FormState) -> List[Field]:
    '''Shows each optimizer argument as a dropdown of optax optimizers, and the settings
    of the optimizer chosen for each optimizer_kwargs table as that table's settings.'''
    by_name = {field.name: field for field in fields}

    def chosen(name):
        text = state.text(section_id, option, name)
        value = by_name[name].default if text is None or not text.strip() else text.strip()
        return getattr(value, '__name__', value)

    result = []
    for field in fields:
        if field.name in OPTIMIZER_ARGS:
            options = optax_optimizers()
            if field.default is None:
                options = ['None'] + options
            field = dataclasses.replace(field, options=options)
        elif field.name.startswith(OPTIMIZER_KWARGS):
            own = 'optimizer' + field.name[len(OPTIMIZER_KWARGS):]
            name = chosen(own) if own in by_name else None
            if name in (None, 'None') and 'optimizer' in by_name:
                name = chosen('optimizer')
            nested = _optax_fields(name) if name in optax_optimizers() else None
            field = dataclasses.replace(field, nested=nested)
        result.append(field)
    return result


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
        self.weight_files = None if online else WEIGHT_FILES
        self.planners = concrete_subclasses(planner, planner.JaxPlanner)
        self.plans = concrete_subclasses(plan, plan.JaxPlan)
        self.compilers = {name: obj for (name, obj) in vars(logic).items()
                          if isinstance(obj, type) and obj.__module__ == logic.__name__
                          and issubclass(obj, logic.JaxRDDLCompilerWithGrad)
                          and 'Compiler' in name}
        self.base_planner_args = set(
            inspect.signature(planner.JaxPlanner.__init__).parameters)
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
        return fields_with_traced_kwargs(
            self.planners[option], TRACE_MODULES,
            NOT_CONFIGURABLE_PLANNER | self.base_planner_args)

    @functools.lru_cache(maxsize=None)
    def _plan_fields(self, option: str) -> List[Field]:
        return fields_with_traced_kwargs(self.plans[option], TRACE_MODULES)

    @functools.lru_cache(maxsize=None)
    def _optimize_fields(self) -> List[Field]:
        fields = signature_fields(
            planner.JaxPlanner.optimize_generator, NOT_CONFIGURABLE_OPTIMIZE)
        names = {field.name for field in fields}
        fields += [field for field in signature_fields(
                        self.controller, NOT_CONFIGURABLE_OPTIMIZE)
                   if field.name not in names]
        return fields

    def _default_auxiliary(self, state: FormState) -> str:
        default = _default_of(self._planner_class(state), 'auxiliary')
        return type(default).__name__ if isinstance(default, planner.JaxPlanner) else 'None'

    def _make_sections(self) -> List[Section]:
        default_compiler = _default_of(planner.JaxPlanner, 'compiler')
        compiler = Section(
            'compiler', '[Compiler]', chooser='method',
            fields=lambda option, state: self._compiler_fields(option),
            options=lambda state: sorted(self.compilers),
            default_option=lambda state: getattr(default_compiler, '__name__', None))
        self._planner_section = planners = Section(
            'planner', '[Planner]', chooser='planner',
            fields=lambda option, state: with_optimizer_choices(
                self._planner_fields(option), 'planner', option, state),
            options=lambda state: sorted(self.planners),
            default_option=lambda state: 'JaxBackpropPlanner')
        auxiliary = Section(
            'auxiliary', '[Planner] auxiliary planner', chooser='auxiliary',
            fields=lambda option, state: with_optimizer_choices(
                self._auxiliary_fields(option), 'auxiliary', option, state),
            options=lambda state: ['None'] + sorted(self.planners),
            default_option=self._default_auxiliary, scope=self._planner_scope)
        plans = Section(
            'plan', '[Planner] method (plan or policy)', chooser='method',
            fields=lambda option, state: self._plan_fields(option),
            options=lambda state: sorted(self.plans),
            default_option=lambda state: 'JaxStraightLinePlan')
        optimize = Section(
            'optimize', '[Optimize]', fields=lambda option, state: self._optimize_fields())
        return [planners, auxiliary, plans, optimize, compiler]

    def sections(self) -> List[Section]:
        return self._sections

    # ===========================================================================
    # configs
    # ===========================================================================

    def initial_state(self) -> FormState:
        name = 'default_replan.cfg' if self.online else 'default_slp.cfg'
        path = os.path.join(
            os.path.dirname(pyRDDLGym_jax.__file__), 'examples', 'configs', name)
        if os.path.isfile(path):
            with open(path) as file:
                return self.from_config(file.read())
        return FormState()

    def to_config(self, state: FormState) -> str:
        compiler, planners, auxiliary, plans = (
            self.section(name) for name in ('compiler', 'planner', 'auxiliary', 'plan'))
        compiler_values = {'method': compiler.option(state), 
                           **self.changed(state, 'compiler')}

        planner_values = {'planner': planners.option(state), 'method': plans.option(state)}
        plan_kwargs = self.changed(state, 'plan')
        if plan_kwargs:
            planner_values['method_kwargs'] = plan_kwargs
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
                                             ('auxiliary', planner_values, 'auxiliary')]:
            if key in values_of:
                option = values_of.pop(key)
                option = 'None' if option is None else str(option)
                self.section(section_id).choose(state, option)

        def pop_dict(key):
            value = planner_values.get(key)
            if value is None or isinstance(value, dict):
                planner_values.pop(key, None)
                return value or {}
            return {}

        assign(state, self.section('compiler'), compiler_values)
        assign(state, self.section('plan'), pop_dict('method_kwargs'))
        assign(state, self.section('auxiliary'), pop_dict('auxiliary_kwargs'))
        assign(state, self.section('planner'), planner_values)
        assign(state, self.section('optimize'), values.get('Optimize', {}))
        return state

    # ===========================================================================
    # running
    # ===========================================================================

    def env_args(self, state: FormState) -> Dict[str, Any]:
        return {'vectorized': True}

    def build_policy(self, env, state: FormState, progress=None):
        planner_args, _, train_args = config.load_config_from_string(self.to_config(state))
        if 'dashboard' in planner_args:
            planner_args['dashboard'].launch()
        jax_planner = planner.create_planner(
            rddl=env.model, dashboard_viz=getattr(env, '_visualizer', None), **planner_args)
        if progress is not None:
            online = self.controller is controller.JaxOnlineController
            _report_training(jax_planner, progress, 'Planning' if online else 'Training')
        return self.controller(jax_planner, **train_args)


    def save_weights(self, policy, path: str) -> None:
        '''Writes the file JaxOfflineController(save_path=path) writes after training.'''
        contents = {'params': policy.params, 'hyperparams': policy.eval_hyperparams}
        with open(path, 'wb') as file:
            pickle.dump(contents, file)

    def load_weights(self, state: FormState, path: str) -> None:
        section = self.section('optimize')
        state.set_text(section.id, section.option(state), 'params', format_value(path))


def _report_training(jax_planner, progress, caption: str) -> None:
    '''Reports every iteration of the planner's training to progress.'''
    generate = jax_planner.optimize_generator

    def describe(callback) -> str:
        test = np.ravel(callback['test_return'])
        index = int(np.argmax(test))
        train = np.ravel(callback['train_return'])[index]
        return (f'{caption} {int(callback["progress"])}% · '
                f'iter {callback["iteration"]} · {callback["elapsed_time"]:.1f} s · '
                f'train {number(train)} · test {number(test[index])} · '
                f'best {number(callback["best_return"])}')

    def optimize_generator(*args, **kwargs):
        for callback in generate(*args, **kwargs):
            progress.training(lambda: describe(callback))
            yield callback
    jax_planner.optimize_generator = optimize_generator
