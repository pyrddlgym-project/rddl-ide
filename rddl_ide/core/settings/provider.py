'''Base class of the baselines that the policy pane shows as a settings form.'''
import configparser
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rddl_ide.core.settings.introspect import signature_fields, trace_kwargs_target
from rddl_ide.core.settings.model import (
    Field, FormState, Section, changed_values, config_literal, format_value, parse_value
)

HEADER = '# rddl-ide: {}'
_HEADER_PATTERN = re.compile(r'^\s*#\s*rddl-ide:\s*(\S+)')


def config_kind(text: str) -> Optional[str]:
    '''Returns the provider kind written in the first line of a config, if any.'''
    first = text.lstrip().splitlines()[0] if text.strip() else ''
    match = _HEADER_PATTERN.match(first)
    return match.group(1) if match else None


def read_config(text: str) -> Dict[str, Dict[str, Any]]:
    '''Reads a config (INI with Python literal values) into {section: {key: value}}.'''
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.read_string(text)
    return {section: {key: parse_value(value) for (key, value) in parser.items(section)}
            for section in parser.sections()}


def write_config(kind: str, sections: Sequence[Tuple[str, Dict[str, Any]]]) -> str:
    '''Writes a config: a header naming the provider kind, then each section's values.'''
    lines = [HEADER.format(kind)]
    for (name, values) in sections:
        lines.append('')
        lines.append(f'[{name}]')
        lines.extend(f'{key}={config_literal(value)}' for (key, value) in values.items())
    return '\n'.join(lines) + '\n'


def fields_with_traced_kwargs(obj, modules, exclude=frozenset()) -> List[Field]:
    '''The settings of a class or function, where each **kwargs dictionary setting whose
    target can be traced in the given modules gets that target's settings as a nested
    table.'''
    fields = signature_fields(obj, exclude)
    for field in fields:
        if 'kwargs' in field.name:
            target = trace_kwargs_target(modules, field.name)
            if target is not None:
                field.nested = signature_fields(target)
            # TODO: add trace hints to pyRDDLGym-jax (and the other packages) so that
            # **kwargs settings whose target is chosen at run time (utility_kwargs,
            # time_embedding_kwargs, reduce_on_plateau_kwargs, ...) also get a nested
            # table; until then they are dictionaries the user types in.
    return fields


def assign(state: FormState, section: Section, values: Dict[str, Any]) -> None:
    '''Puts values read from a config into the form fields of a section; values that
    match no field are kept in the section's additional settings.'''
    option = section.option(state)
    fields = {field.name: field for field in section.fields(option, state)}
    extras = {}
    for (name, value) in values.items():
        field = fields.get(name)
        if field is None:
            extras[name] = value
        elif field.nested is not None and isinstance(value, dict) and \
                set(value) <= {sub.name for sub in field.nested}:
            for (sub, sub_value) in value.items():
                state.set_text(section.id, option, f'{name}.{sub}', format_value(sub_value))
        elif field.nested is not None and value is not None:
            extras[name] = value
        else:
            state.set_text(section.id, option, name, format_value(value))
    if extras:
        state.set_extra(section.id, format_value(extras))


class Provider:
    '''A baseline shown as a settings form: its sections, how the form becomes a config
    and a policy, and how a config becomes a form again.'''

    kind = ''
    title = ''

    def sections(self) -> List[Section]:
        raise NotImplementedError

    def initial_state(self) -> FormState:
        return FormState()

    def env_args(self, state: FormState) -> Dict[str, Any]:
        return {}

    def to_config(self, state: FormState) -> str:
        raise NotImplementedError

    def from_config(self, text: str) -> FormState:
        raise NotImplementedError

    def build_policy(self, env, state: FormState):
        raise NotImplementedError

    def section(self, section_id: str) -> Section:
        return next(s for s in self.sections() if s.id == section_id)

    def changed(self, state: FormState, section_id: str) -> Dict[str, Any]:
        return changed_values(state, self.section(section_id))
