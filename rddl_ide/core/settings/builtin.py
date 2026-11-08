'''The agents built into pyRDDLGym as a settings form.'''
import functools
import inspect
from typing import List

from pyRDDLGym.core import policy

from rddl_ide.core.settings.introspect import concrete_subclasses, signature_fields
from rddl_ide.core.settings.model import Field, FormState, Section
from rddl_ide.core.settings.provider import Provider, assign, read_config, write_config

# arguments the IDE supplies from the environment, by name
SUPPLIED_BY_ENV = {
    'env': lambda env: env,
    'action_space': lambda env: env.action_space,
}


class BuiltinAgentProvider(Provider):

    kind = 'builtin'
    title = 'Built-in agent'

    def __init__(self) -> None:
        self.agents = concrete_subclasses(policy, policy.BaseAgent)
        self._sections = [Section(
            'agent', '[Agent]', chooser='agent',
            fields=lambda option, state: self._agent_fields(option),
            options=lambda state: sorted(self.agents),
            default_option=lambda state: 'NoOpAgent')]

    @functools.lru_cache(maxsize=None)
    def _agent_fields(self, option: str) -> List[Field]:
        return signature_fields(self.agents[option], set(SUPPLIED_BY_ENV))

    def sections(self) -> List[Section]:
        return self._sections

    def to_config(self, state: FormState) -> str:
        values = {'agent': self.section('agent').option(state), **self.changed(state, 'agent')}
        return write_config(self.kind, [('Agent', values)])

    def from_config(self, text: str) -> FormState:
        values = dict(read_config(text).get('Agent', {}))
        state = FormState()
        if 'agent' in values:
            self.section('agent').choose(state, str(values.pop('agent')))
        assign(state, self.section('agent'), values)
        return state

    def build_policy(self, env, state: FormState, progress=None):
        cls = self.agents[self.section('agent').option(state)]
        kwargs = self.changed(state, 'agent')
        parameters = inspect.signature(cls.__init__).parameters
        for (name, supply) in SUPPLIED_BY_ENV.items():
            if name in parameters:
                kwargs[name] = supply(env)
        return cls(**kwargs)
