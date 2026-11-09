'''Runs an episode of a policy one step at a time, keeping what each step shows: the
state, the action taken, the intermediate fluents, the reward and the picture.'''
import numpy as np
import os
import tempfile
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

from rddl_ide.core.execution import RunOptions, close_env, make_environment, save_log

NUMERIC = ('bool', 'int', 'real')

Rows = Dict[str, List[Tuple[str, Any]]]


class Snapshot(NamedTuple):
    step: int
    horizon: int
    reward: Optional[float]
    total: float
    done: bool
    sections: List[Tuple[str, Rows]]
    highlighted: Set[Tuple[str, str]]
    image: Any


class Stepper:
    '''The environment and policy of a run, stepped through by step() after restart().
    Raises what pyRDDLGym or the policy raise; close() when done.'''

    def __init__(self, domain, instance, build_policy, required_env_args, viz,
                 options: RunOptions, progress):
        self.options = options
        self._folder = tempfile.TemporaryDirectory()
        self._log_path = os.path.join(self._folder.name, 'simulation')
        self.env = None
        self.snapshot: Optional[Snapshot] = None
        self.done = True
        try:
            (self.env, self.render) = make_environment(
                domain, instance, required_env_args, viz, options, self._log_path)
            self.model = self.env.model
            self.policy = progress.policy = build_policy(self.env)
        except BaseException:
            self.close()
            raise
        self._noop = self._rows(self.env.sampler.noop_actions)

    # ===========================================================================
    # running
    # ===========================================================================

    def restart(self) -> Snapshot:
        '''Starts the episode again, from the seed of the options (if any).'''
        self.policy.reset()
        (self.state, _) = self.env.reset(seed=self.options.seed)
        (self.steps, self.total, self.discount) = (0, 0.0, 1.0)
        self.done = bool(self.env.done)
        self.snapshot = self._snapshot(None, None, {})
        return self.snapshot

    def step(self) -> Snapshot:
        '''Takes the action of the policy in the current state.'''
        action = self.policy.sample_action(self.state)
        (state, reward, terminated, truncated, info) = self.env.step(action)
        self.state = state
        reward = float(reward)
        self.steps += 1
        self.total += reward * self.discount
        self.discount *= self.env.discount
        self.done = bool(terminated or truncated)
        self.snapshot = self._snapshot(action, reward, info)
        return self.snapshot

    def close(self) -> str:
        '''Closes the environment, and returns what became of the simulation log.'''
        if self._folder is None:
            return ''
        close_env(self.env)
        self.env = None
        note = save_log(self._log_path, self.options.log_file)
        self._folder.cleanup()
        self._folder = None
        return note

    # ===========================================================================
    # what a step shows
    # ===========================================================================

    def _snapshot(self, action, reward, info) -> Snapshot:
        env, model = self.env, self.model
        sections = [('State', self._rows(env.state))]
        if action is not None:
            sections.append(
                ('Action', self._rows(env.sampler.prepare_actions_for_sim(action))))
            subs = getattr(env.sampler, 'subs', {})
            interm = {name: subs[name] for (name, kind) in model.variable_types.items()
                      if kind in ('interm-fluent', 'derived-fluent') and name in subs}
            if interm:
                sections.append(('Intermediate', self._rows(interm)))
        if model.observ_fluents and action is not None:
            sections.append(('Observation', self._rows(self.state)))
        probes = (info or {}).get('probes')
        if probes:
            sections.append(('Probes', self._rows(probes)))

        highlighted = set()
        before = dict(self.snapshot.sections) if self.snapshot and action is not None \
            else {}
        for (section, rows) in sections:
            if section == 'Action':
                compare = self._noop
            elif section in before:
                compare = before[section]
            else:
                continue
            values = {grounding: value for pairs in compare.values()
                      for (grounding, value) in pairs}
            highlighted.update((section, grounding) for pairs in rows.values()
                               for (grounding, value) in pairs
                               if grounding in values and values[grounding] != value)
        image = env.render(to_display=False) if self.render else None
        return Snapshot(self.steps, env.horizon, reward, self.total, self.done, sections,
                        highlighted, image)

    def _rows(self, values: Dict[str, Any]) -> Rows:
        '''The values, by fluent (lifted, as arrays) or by grounding, as rows of python
        values, with the objects of enumerated fluents by name.'''
        model = self.model
        rows: Rows = {}
        for (name, value) in values.items():
            if name in model.variable_groundings:
                pairs = model.ground_var_with_values(name, self._objects(name, value))
                var = name
            else:
                (var, _) = model.parse_grounded(name)
                pairs = [(name, self._objects(var, value))]
            rows.setdefault(var, []).extend(
                (_label(grounding), _python(v)) for (grounding, v) in pairs)
        return rows

    def _objects(self, var: str, value):
        '''Object names in place of the indices pyRDDLGym keeps for enumerated values.'''
        ptype = self.model.variable_ranges.get(var)
        if ptype is None or ptype in NUMERIC:
            return value
        array = np.asarray(value)
        if not np.issubdtype(array.dtype, np.integer):
            return value
        return self.model.index_to_object_string_array(ptype, array)


def _label(grounding: str) -> str:
    '''rlevel(t1) for rlevel___t1.'''
    from pyRDDLGym.core.compiler.model import RDDLPlanningModel
    (var, objects) = RDDLPlanningModel.parse_grounded(grounding)
    return f'{var}({", ".join(objects)})' if objects else var


def _python(value):
    return value.item() if isinstance(value, np.generic) else value
