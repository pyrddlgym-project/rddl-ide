'''The baselines shown as settings forms, in Baseline menu order. Each provider is
imported only when chosen, so a package that is not installed only affects its entry.'''
from typing import Callable, List, Optional, Tuple

from rddl_ide.core.settings.provider import Provider, config_kind, read_config


def _builtin() -> Provider:
    from rddl_ide.core.settings.builtin import BuiltinAgentProvider
    return BuiltinAgentProvider()


def _jaxplan_offline() -> Provider:
    from rddl_ide.core.settings.jaxplan import JaxPlanProvider
    return JaxPlanProvider(online=False)


def _jaxplan_online() -> Provider:
    from rddl_ide.core.settings.jaxplan import JaxPlanProvider
    return JaxPlanProvider(online=True)


def _gurobi_online() -> Provider:
    from rddl_ide.core.settings.gurobi import GurobiProvider
    return GurobiProvider()


def _sb3() -> Provider:
    from rddl_ide.core.settings.sb3 import StableBaselinesProvider
    return StableBaselinesProvider()


PROVIDERS: List[Tuple[str, str, Callable[[], Provider]]] = [
    ('builtin', 'Built-in agent', _builtin),
    ('jaxplan-offline', 'JaxPlan (offline)', _jaxplan_offline),
    ('jaxplan-online', 'JaxPlan (online)', _jaxplan_online),
    ('gurobi-online', 'Gurobi (online)', _gurobi_online),
    ('sb3', 'Stable-Baselines3', _sb3),
]

# sections that identify a config written without the rddl-ide header
_SECTIONS_OF_KIND = [
    ('jaxplan-offline', {'Compiler', 'Planner', 'Optimize'}),
    ('gurobi-online', {'Gurobi', 'Optimizer'}),
    ('builtin', {'Agent'}),
    ('sb3', {'Algorithm'}),
]


def title_of(kind: str) -> str:
    return next(title for (k, title, _) in PROVIDERS if k == kind)


def create(kind: str) -> Provider:
    return next(factory for (k, _, factory) in PROVIDERS if k == kind)()


def detect_kind(text: str) -> Optional[str]:
    '''Which form a config belongs to: from its rddl-ide header, else from its sections.'''
    kind = config_kind(text)
    if kind in {k for (k, _, _) in PROVIDERS}:
        return kind
    sections = set(read_config(text))
    for (kind, required) in _SECTIONS_OF_KIND:
        if required <= sections:
            return kind
    return None
