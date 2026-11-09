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
        include_non_fluents=include_non_fluents)
    reward: Dict[str, set] = {}
    analysis._update_call_graph(reward, REWARD, model.reward, include_non_fluents)
    graph[REWARD] = sorted(reward.get(REWARD, ()))
    levels = analysis.compute_levels()

    def node(name, kind, column):
        if kind == REWARD:
            return Node(name, kind, column, f'{REWARD} : real')
        params = model.variable_params.get(name) or []
        signature = name + (f'({", ".join(params)})' if params else '')
        prange = model.variable_ranges.get(name)
        return Node(name, kind, column, f'{signature} : {prange}' if prange else signature)

    types = model.variable_types
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
