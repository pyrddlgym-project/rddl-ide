'''The model behind a settings form, independent of any UI: the fields of each section,
how values are shown and parsed, and which values the user changed.'''
import ast
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


class _Missing:
    '''Default of an argument that has none, i.e. a required argument.'''

    def __repr__(self):
        return 'MISSING'


MISSING = _Missing()
_UNSET = object()


@dataclass
class Field:
    '''One setting: an argument name, its default, and optionally the settings of the
    function that a **kwargs dictionary setting is passed to, or the names it can be set
    to (shown as a dropdown, and written to configs as strings).'''
    name: str
    default: Any = MISSING
    nested: Optional[List['Field']] = None
    options: Optional[List[str]] = None

    @property
    def required(self) -> bool:
        return self.default is MISSING


def format_value(value: Any) -> str:
    '''Shows a value as it would be written in a config file.'''
    if value is MISSING:
        return ''
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return str(value)
    text = repr(value)
    try:
        if not isinstance(value, str) and parse_value(text) == value or \
                isinstance(value, str) and ast.literal_eval(text) == value:
            return text
    except Exception:
        pass
    name = getattr(value, '__name__', None)
    qualname = getattr(value, '__qualname__', '') or ''
    if callable(value) and name and name != '<lambda>' and '<locals>' not in qualname:
        return name
    return '<default>'


def config_literal(value: Any) -> str:
    '''Writes a value so that the packages' config loaders (ast.literal_eval) read it
    back: like repr, except that infinities are written as 1e309.'''
    if isinstance(value, float) and math.isinf(value):
        return '1e309' if value > 0 else '-1e309'
    if isinstance(value, tuple):
        items = [config_literal(v) for v in value]
        return '(' + ', '.join(items) + (',)' if len(items) == 1 else ')')
    if isinstance(value, list):
        return '[' + ', '.join(config_literal(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{' + ', '.join(f'{config_literal(k)}: {config_literal(v)}'
                               for (k, v) in value.items()) + '}'
    return repr(value)


def parse_value(text: str) -> Any:
    '''Parses a value typed by the user: a Python literal, inf/nan, or else a string.'''
    text = text.strip()
    special = {'inf': math.inf, '+inf': math.inf, '-inf': -math.inf, 'nan': math.nan}
    if text in special:
        return special[text]
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        pass
    try:  # literals containing inf or nan, e.g. (0.0, inf)
        tree = _InfToConstant().visit(ast.parse(text, mode='eval'))
        return ast.literal_eval(tree)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return text


class _InfToConstant(ast.NodeTransformer):

    def visit_Name(self, node):
        if node.id in ('inf', 'nan'):
            return ast.copy_location(ast.Constant(float(node.id)), node)
        return node


class FormState:
    '''What the user chose and typed. Values are kept per section and per chosen option,
    so switching a class away and back restores the values typed for it.'''

    def __init__(self) -> None:
        self.choices: Dict[str, str] = {}
        self.texts: Dict[tuple, str] = {}
        self.extras: Dict[str, str] = {}

    def choice(self, key: str) -> Optional[str]:
        return self.choices.get(key)

    def set_choice(self, key: str, option: str) -> None:
        self.choices[key] = option

    def text(self, section: str, option: Optional[str], path: str) -> Optional[str]:
        return self.texts.get((section, option, path))

    def set_text(self, section: str, option: Optional[str], path: str, text: str) -> None:
        self.texts[(section, option, path)] = text

    def extra(self, section: str) -> str:
        return self.extras.get(section, '')

    def set_extra(self, section: str, text: str) -> None:
        self.extras[section] = text


def _no_options(state: FormState) -> List[str]:
    return []


def _no_default(state: FormState) -> Optional[str]:
    return None


def _no_scope(state: FormState) -> str:
    return ''


@dataclass
class Section:
    '''A group of settings, optionally headed by a class chooser whose chosen option
    decides the fields. The choice is remembered per scope (e.g. per planner).'''
    id: str
    title: str
    fields: Callable[[Optional[str], FormState], List[Field]]
    chooser: Optional[str] = None
    options: Callable[[FormState], List[str]] = _no_options
    default_option: Callable[[FormState], Optional[str]] = _no_default
    scope: Callable[[FormState], str] = _no_scope

    def choice_key(self, state: FormState) -> str:
        return f'{self.id}@{self.scope(state)}'

    def option(self, state: FormState) -> Optional[str]:
        if self.chooser is None:
            return None
        options = self.options(state)
        chosen = state.choice(self.choice_key(state))
        if chosen in options:
            return chosen
        default = self.default_option(state)
        if default in options or not options:
            return default
        return options[0]

    def choose(self, state: FormState, option: str) -> None:
        state.set_choice(self.choice_key(state), option)


def is_changed(text: Optional[str], field: Field) -> bool:
    '''Whether the text typed for a field sets a value other than its default.'''
    return _parsed_change(text, field) is not _UNSET


def _changed_value(state, section_id, option, path, field) -> Any:
    return _parsed_change(state.text(section_id, option, path), field)


def _parsed_change(text: Optional[str], field: Field) -> Any:
    if text is None or not text.strip():
        return _UNSET
    if field.default is not MISSING and text.strip() == format_value(field.default):
        return _UNSET
    value = parse_value(text)
    try:
        if field.default is not MISSING and value == field.default:
            return _UNSET
    except Exception:
        pass
    return value


def changed_values(state: FormState, section: Section,
                   fields: Optional[List[Field]]=None) -> Dict[str, Any]:
    '''Returns the parsed values of the section that differ from their defaults, plus the
    section's additional settings. Raises ValueError naming a required value that is
    missing (a nested required value only counts once its table is used).'''
    option = section.option(state)
    if fields is None:
        fields = section.fields(option, state)
    values, missing = {}, []
    for field in fields:
        if field.nested is None:
            value = _changed_value(state, section.id, option, field.name, field)
            if value is not _UNSET:
                values[field.name] = value
            elif field.required:
                missing.append(field.name)
            continue
        nested = {}
        for sub in field.nested:
            value = _changed_value(state, section.id, option, f'{field.name}.{sub.name}', sub)
            if value is not _UNSET:
                nested[sub.name] = value
        if nested:
            for sub in field.nested:
                if sub.required and sub.name not in nested:
                    raise ValueError(f'{section.title}: {field.name}.{sub.name} is required.')
            values[field.name] = nested
    if missing:
        raise ValueError(f'{section.title}: {missing[0]} is required.')
    extra = state.extra(section.id).strip()
    if extra:
        parsed = parse_value(extra)
        if not isinstance(parsed, dict):
            raise ValueError(f'{section.title}: additional settings must be a dict, '
                             f'e.g. {{\'name\': value}}.')
        values.update(parsed)
    return values
