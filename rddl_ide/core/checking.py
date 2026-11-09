'''Checks a domain and instance without running them.'''
import os
import tempfile
import warnings
from typing import List, NamedTuple

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
    '''The summary parts and detail lines on the bounds the preconditions put on the
    numeric action fluents, and on the preconditions that are not such bounds.'''
    from pyRDDLGym.core.constraints import RDDLConstraints
    from pyRDDLGym.core.debug.decompiler import RDDLDecompiler

    model = env.model
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        constraints = RDDLConstraints(env.sampler)
    bounds = constraints.bounds
    numeric = [name for name in model.action_fluents
               if model.variable_ranges[name] in ('real', 'int')]
    parts, details = [], []
    if numeric:
        rows, bounded, total = [], 0, 0
        for name in numeric:
            pairs = [bounds[grounded] for grounded in model.variable_groundings[name]]
            bounded += sum(abs(low) < float('inf') and abs(high) < float('inf')
                           for (low, high) in pairs)
            total += len(pairs)
            params = model.variable_params[name]
            lifted = f'{name}({", ".join("?" + ptype for ptype in params)})' \
                if params else name
            rows.append(f'  {lifted} ∈ [{_end([low for (low, _) in pairs])}, '
                        f'{_end([high for (_, high) in pairs])}]')
        parts.append(f'{bounded} of {total} numeric actions bounded')
        details += ['Action bounds from the preconditions:'] + _listed(rows)
    loose = [index for (index, is_box) in enumerate(constraints.is_box_preconditions)
             if not is_box]
    if loose:
        parts.append(f'{len(loose)} precondition{"s" if len(loose) > 1 else ""} '
                     f'not a bound')
        rows = []
        for index in loose:
            text = ' '.join(RDDLDecompiler().decompile_expr(
                model.preconditions[index]).split())
            if len(text) > MAX_EXPRESSION:
                text = text[:MAX_EXPRESSION - 1] + '…'
            rows.append(f'  {index + 1}. {text}')
        if details:
            details.append('')
        details += ['Preconditions that are not a bound on one action fluent '
                    '(so not part of the action space):'] + _listed(rows)
    return parts, details


def check(domain: str, instance: str) -> CheckResult:
    '''Raises the error of pyRDDLGym if the RDDL texts have one, else returns a summary
    of the model, e.g. its numbers of grounded state and action fluents and the bounds
    of its actions.'''
    from pyRDDLGym.core.env import RDDLEnv

    with tempfile.TemporaryDirectory() as folder:
        paths = [os.path.join(folder, name) for name in ('domain.rddl', 'instance.rddl')]
        for (path, text) in zip(paths, (domain, instance)):
            with open(path, 'w', encoding='utf-8') as file:
                file.write(text)
        env = RDDLEnv(*paths)
    try:
        model = env.model
        counts = [(len(model.ground_vars_with_values(fluents)), name)
                  for (fluents, name) in ((model.state_fluents, 'state'),
                                          (model.action_fluents, 'action'),
                                          (model.observ_fluents, 'observation'))]
        parts = [f'{count} {name}' for (count, name) in counts
                 if count or name != 'observation']
        (bound_parts, details) = _action_bounds(env)
        summary = ' · '.join([
            'No errors', model.domain_name, f'{", ".join(parts)} fluents',
            f'horizon {model.horizon}'] + bound_parts)
        return CheckResult(summary, '\n'.join(details))
    finally:
        env.close()
