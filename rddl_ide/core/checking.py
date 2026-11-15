'''Checks a domain and instance without running them.'''
import math
import os
import re
import tempfile
import warnings
from typing import Dict, List, NamedTuple, Tuple

from rddl_ide.core.dependencies import dependency_graph
from rddl_ide.core.errorlocation import strip_ansi

MAX_LISTED = 12
MAX_EXPRESSION = 100


class CheckResult(NamedTuple):
    summary: str
    details: str
    

def _number(value) -> str:
    return f'{float(value):.5g}'


def _end(values) -> str:
    '''One end of the bounds of the groundings of a fluent, as a value or a range.'''
    (low, high) = (min(values), max(values))
    return _number(low) if low == high else f'{_number(low)}…{_number(high)}'


def _listed(lines: List[str]) -> List[str]:
    if len(lines) > MAX_LISTED:
        lines = lines[:MAX_LISTED - 1] + [f'  … {len(lines) - MAX_LISTED + 1} more']
    return lines


def _action_bounds(env):
    '''The summary parts, and the rows, of the bounds the preconditions put on the
    numeric action fluents and of the preconditions that are not such bounds.'''
    from pyRDDLGym.core.constraints import RDDLConstraints
    from pyRDDLGym.core.debug.decompiler import RDDLDecompiler

    model = env.model
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        constraints = RDDLConstraints(env.sampler)
    bounds = constraints.bounds
    numeric = [name for name in model.action_fluents
               if model.variable_ranges[name] in ('real', 'int')]
    parts, bound_rows, loose_rows = [], [], []
    if numeric:
        bounded, total = 0, 0
        for name in numeric:
            pairs = [bounds[grounded] for grounded in model.variable_groundings[name]]
            bounded += sum(abs(low) < float('inf') and abs(high) < float('inf')
                           for (low, high) in pairs)
            total += len(pairs)
            params = model.variable_params[name]
            lifted = f'{name}({", ".join("?" + ptype for ptype in params)})' \
                if params else name
            bound_rows.append(f'{lifted} ∈ [{_end([low for (low, _) in pairs])}, '
                              f'{_end([high for (_, high) in pairs])}]')
        parts.append(f'{bounded} of {total} numeric actions bounded')
    loose = [index for (index, is_box) in enumerate(constraints.is_box_preconditions)
             if not is_box]
    if loose:
        parts.append(f'{len(loose)} precondition{"s" if len(loose) > 1 else ""} '
                     f'not a bound')
        for index in loose:
            text = ' '.join(RDDLDecompiler().decompile_expr(
                model.preconditions[index]).split())
            if len(text) > MAX_EXPRESSION:
                text = text[:MAX_EXPRESSION - 1] + '…'
            loose_rows.append(f'{index + 1}. {text}')
    return parts, _listed(bound_rows), _listed(loose_rows)


def _environment(domain: str, instance: str):
    '''The pyRDDLGym environment of the RDDL texts, raising its error if they have one.'''
    from pyRDDLGym.core.env import RDDLEnv

    with tempfile.TemporaryDirectory() as folder:
        paths = [os.path.join(folder, name) for name in ('domain.rddl', 'instance.rddl')]
        for (path, text) in zip(paths, (domain, instance)):
            with open(path, 'w', encoding='utf-8') as file:
                file.write(text)
        return RDDLEnv(*paths)


def _distributions(expr, found: set) -> set:
    '''The names of the distributions sampled in the expression.'''
    from pyRDDLGym.core.parser.expr import Expression

    if isinstance(expr, (tuple, list)):
        for arg in expr:
            _distributions(arg, found)
    elif isinstance(expr, Expression) and not expr.is_constant_expression():
        if expr.etype[0] in ('randomvar', 'randomvector'):
            found.add(expr.etype[1])
        _distributions(expr.args, found)
    return found


def _initial_check(sampler) -> str:
    '''Whether the initial state satisfies the invariants, the no-op action the
    preconditions, and whether the initial state is terminal.'''
    sampler.reset()
    try:
        sampler.check_state_invariants()
        sampler.check_action_preconditions(dict(sampler.noop_actions))
    except Exception as error:
        message = strip_ansi(str(error)).strip()
        found = re.match(r'(Invariant|Precondition) (\d+) is not satisfied', message)
        if found is None:
            return '✗ ' + message.splitlines()[0]
        (kind, index) = (found[1].lower(), int(found[2]) + 1)
        return f'✗ the initial state violates {kind} {index}' if kind == 'invariant' \
            else f'✗ the no-op action violates {kind} {index}'
    terminal = sampler.check_terminal_states()
    return '✓ invariants hold and the no-op action satisfies the preconditions' + (
        ', but the state is terminal' if terminal else '')


def summarize(domain: str, instance: str) -> List[Tuple[str, List[Tuple[str, str]]]]:
    '''The size and constraints of the problem of the RDDL texts, as sections of
    (label, text) rows, raising the error of pyRDDLGym if they have one.'''
    env = _environment(domain, instance)
    try:
        model = env.model
        types = model.variable_types
        problem = [('Domain', model.domain_name), ('Instance', model.instance_name),
                   ('Horizon', str(model.horizon)),
                   ('Discount', _number(model.discount))]
        objects = model.type_to_objects
        if objects:
            problem.append(('Objects', ' · '.join(
                f'{ptype} {len(names)}' for (ptype, names) in objects.items())))

        fluents = []
        for (kind, label) in (('non-fluent', 'Non-fluents'), ('state-fluent', 'State'),
                              ('action-fluent', 'Action'), ('interm-fluent', 'Intermediate'),
                              ('observ-fluent', 'Observation')):
            names = [name for (name, t) in types.items() if t == kind]
            if names or kind in ('state-fluent', 'action-fluent'):
                grounded = sum(len(model.variable_groundings[name]) for name in names)
                fluents.append((label, f'{grounded} grounded, {len(names)} lifted'))
        ranges: Dict[str, int] = {}
        for name in model.action_fluents:
            prange = model.variable_ranges[name]
            ranges[prange] = ranges.get(prange, 0) + len(model.variable_groundings[name])
        total = sum(ranges.values())
        most = min(model.max_allowed_actions, total)
        space = ', '.join(f'{count} {prange}' for (count, prange) in
                          sorted(((c, r) for (r, c) in ranges.items()), reverse=True))
        if set(ranges) == {'bool'}:
            joint = sum(math.comb(total, k) for k in range(most + 1))
            space += f' → {joint:,} joint actions' if joint < 10 ** 9 else \
                f' → {joint:.3g} joint actions'
        if most < total:
            space += f' (at most {most} not default)'
        fluents.append(('Action space', space or 'no actions'))
        sampled: Dict[str, List[str]] = {}
        for (name, expr) in [(name, expr) for (name, (_, expr)) in model.cpfs.items()] + \
                [('reward', model.reward)]:
            for distribution in sorted(_distributions(expr, set())):
                sampled.setdefault(distribution, []).append(name)
        fluents.append(('Stochastic', '\n'.join(
            f'{distribution}: {", ".join(names)}'
            for (distribution, names) in sorted(sampled.items())) or 'none (deterministic)'))

        constraints = [('Count', f'{len(model.preconditions)} preconditions · '
                                 f'{len(model.invariants)} invariants · '
                                 f'{len(model.terminations)} terminations')]
        (_, bound_rows, loose_rows) = _action_bounds(env)
        if bound_rows:
            constraints.append(('Action bounds', '\n'.join(bound_rows)))
        if loose_rows:
            constraints.append(('Not a bound', '\n'.join(loose_rows)))
        constraints.append(('Initial state', _initial_check(env.sampler)))
        irrelevant = [node.name for node in
                      dependency_graph(domain, instance, include_non_fluents=True).nodes
                      if not node.relevant]
        fluents.append(('Irrelevant', ', '.join(irrelevant) or 'none'))
        return [('Problem', problem), ('Fluents', fluents), ('Constraints', constraints)]
    finally:
        env.close()


def check(domain: str, instance: str) -> CheckResult:
    '''Raises the error of pyRDDLGym if the RDDL texts have one, else returns a summary
    of the model.'''
    env = _environment(domain, instance)
    try:
        model = env.model
        counts = [(len(model.ground_vars_with_values(fluents)), name)
                  for (fluents, name) in ((model.state_fluents, 'state'),
                                          (model.action_fluents, 'action'),
                                          (model.observ_fluents, 'observation'))]
        parts = [f'{count} {name}' for (count, name) in counts
                 if count or name != 'observation']
        (bound_parts, bound_rows, loose_rows) = _action_bounds(env)
        details = []
        if bound_rows:
            details += ['Action bounds from the preconditions:'] + \
                [f'  {row}' for row in bound_rows]
        if loose_rows:
            details += [''] if details else []
            details += ['Preconditions that are not a bound on one action fluent '
                        '(so not part of the action space):'] + \
                [f'  {row}' for row in loose_rows]
        summary = ' · '.join([
            'No errors', model.domain_name, f'{", ".join(parts)} fluents',
            f'horizon {model.horizon}'] + bound_parts)
        return CheckResult(summary, '\n'.join(details))
    finally:
        env.close()
