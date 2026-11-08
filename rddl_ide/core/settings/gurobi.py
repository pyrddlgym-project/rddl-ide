'''GurobiPlan (pyRDDLGym-gurobi) as a settings form, read from the installed package.'''
import functools
import os
from typing import List

import gurobipy
import pyRDDLGym_gurobi
from pyRDDLGym_gurobi.core import compiler, planner

from rddl_ide.core.settings.introspect import concrete_subclasses, signature_fields
from rddl_ide.core.settings.model import Field, FormState, Section
from rddl_ide.core.settings.provider import Provider, assign, read_config, write_config

# arguments a config cannot set: objects that the controller supplies
NOT_CONFIGURABLE_COMPILER = {'rddl', 'plan', 'logger', 'model_params'}


@functools.lru_cache(maxsize=None)
def solver_parameters() -> List[Field]:
    '''Every Gurobi parameter with its default, read from an environment that is never
    started, so that no license is needed.'''
    env = gurobipy.Env(empty=True)
    names = sorted(name for name in dir(gurobipy.GRB.Param) if not name.startswith('_'))
    fields = []
    for name in names:
        try:
            fields.append(Field(name, env.getParam(name)))
        except gurobipy.GurobiError:
            continue
    return fields


class GurobiProvider(Provider):

    kind = 'gurobi-online'
    title = 'Gurobi (online)'

    def __init__(self) -> None:
        self.plans = concrete_subclasses(planner, planner.GurobiPlan)
        self._sections = [
            Section('plan', '[Optimizer] method (plan or policy)', chooser='method',
                    fields=lambda option, state: self._plan_fields(option),
                    options=lambda state: sorted(self.plans),
                    default_option=lambda state: 'GurobiStraightLinePlan'),
            Section('optimizer', '[Optimizer]',
                    fields=lambda option, state: self._compiler_fields()),
            Section('gurobi', '[Gurobi] solver parameters',
                    fields=lambda option, state: solver_parameters()),
        ]

    @functools.lru_cache(maxsize=None)
    def _plan_fields(self, option: str) -> List[Field]:
        return signature_fields(self.plans[option])

    @functools.lru_cache(maxsize=None)
    def _compiler_fields(self) -> List[Field]:
        return signature_fields(compiler.GurobiRDDLCompiler, NOT_CONFIGURABLE_COMPILER)

    def sections(self) -> List[Section]:
        return self._sections

    def initial_state(self) -> FormState:
        path = os.path.join(os.path.dirname(pyRDDLGym_gurobi.__file__), 'examples', 'default.cfg')
        if os.path.isfile(path):
            with open(path) as file:
                return self.from_config(file.read())
        return FormState()

    def to_config(self, state: FormState) -> str:
        optimizer = {'method': self.section('plan').option(state)}
        method_kwargs = self.changed(state, 'plan')
        if method_kwargs:
            optimizer['method_kwargs'] = method_kwargs
        optimizer.update(self.changed(state, 'optimizer'))
        return write_config(self.kind, [('Gurobi', self.changed(state, 'gurobi')),
                                        ('Optimizer', optimizer)])

    def from_config(self, text: str) -> FormState:
        values = read_config(text)
        state = FormState()
        optimizer = dict(values.get('Optimizer', {}))
        if 'method' in optimizer:
            self.section('plan').choose(state, str(optimizer.pop('method')))
        method_kwargs = optimizer.get('method_kwargs')
        if method_kwargs is None or isinstance(method_kwargs, dict):
            optimizer.pop('method_kwargs', None)
            assign(state, self.section('plan'), method_kwargs or {})
        assign(state, self.section('optimizer'), optimizer)
        assign(state, self.section('gurobi'), values.get('Gurobi', {}))
        return state

    def build_policy(self, env, state: FormState):
        controller_args = planner.load_config_from_string(self.to_config(state))
        return planner.GurobiOnlineController(rddl=env.model, **controller_args)
