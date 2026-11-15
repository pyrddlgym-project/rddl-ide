'''Which fluents each CPF and the reward of a domain depend on, and the order in which
pyRDDLGym evaluates the CPFs, as a graph in columns.'''
from typing import Dict, List, NamedTuple, Tuple

from rddl_ide.core.grounding import lifted_model

REWARD = 'reward'

# the kinds of the inputs of a step, in the order they are shown
INPUTS = ('non-fluent', 'state-fluent', 'action-fluent')


class Node(NamedTuple):
    name: str
    kind: str
    column: int
    signature: str
    relevant: bool = True


class Graph(NamedTuple):
    nodes: List[Node]
    edges: List[Tuple[str, str]]
    

def dependency_graph(domain: str, instance: str,
                     include_non_fluents: bool=False) -> Graph:
    '''The graph of the domain and instance texts: all state and action fluents (and
    non-fluents, if included) in the first column, and the CPFs in the order of their
    levels of evaluation, ending with the reward.'''
    from pyRDDLGym.core.compiler.levels import RDDLLevelAnalysis

    model = lifted_model(domain, instance)
    analysis = RDDLLevelAnalysis(model)
    graph: Dict[str, List[str]] = analysis.build_call_graph(
        include_non_fluents=include_non_fluents, include_reward=True)
    levels = analysis.compute_levels()
    types = model.variable_types

    # what affects the reward, terminations, preconditions or observations, a state
    # fluent through its next state
    goals: Dict[str, set] = {}
    analysis._update_call_graph(
        goals, REWARD, [model.terminations, model.preconditions], include_non_fluents)
    pending = [REWARD, *goals.get(REWARD, ()),
               *(name for (name, kind) in types.items() if kind == 'observ-fluent')]
    relevant = set()
    while pending:
        name = pending.pop()
        if name not in relevant:
            relevant.add(name)
            pending.extend(graph.get(name, ()))
            if types.get(name) == 'state-fluent':
                pending.append(name + model.NEXT_STATE_SYM)

    def node(name, kind, column):
        if kind == REWARD:
            return Node(name, kind, column, f'{REWARD} : real')
        params = model.variable_params.get(name) or []
        signature = name + (f'({", ".join(params)})' if params else '')
        prange = model.variable_ranges.get(name)
        return Node(
            name, kind, column, f'{signature} : {prange}' if prange else signature,
            name in relevant
        )

    shown = set(INPUTS if include_non_fluents else INPUTS[1:])
    nodes = [node(name, kind, 0) for kind in INPUTS if kind in shown
             for name in sorted(n for (n, t) in types.items() if t == kind)]
    for (level, names) in sorted(levels.items()):
        nodes.extend(node(name, types.get(name, 'interm-fluent'), 1 + level)
                     for name in names)
    nodes.append(node(REWARD, REWARD, 2 + max(levels, default=-1)))
    known = {n.name for n in nodes}
    edges = [(dep, name) for (name, deps) in graph.items() for dep in deps
             if name in known and dep in known]
    return Graph(nodes, edges)
