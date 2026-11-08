'''Reads settings from the installed packages: constructor and function signatures,
the classes a module offers, and where a **kwargs dictionary is passed to.'''
import ast
import functools
import inspect
from types import ModuleType
from typing import Callable, Dict, Iterable, List, Optional

from rddl_ide.core.settings.model import MISSING, Field

__all__ = ['MISSING', 'signature_fields', 'concrete_subclasses', 'trace_kwargs_target']


def signature_fields(obj, exclude: Iterable[str]=frozenset()) -> List[Field]:
    '''Returns the keyword arguments of a function, or of a class constructor including
    those it forwards to its parent classes through **kwargs (the first default found
    along the MRO wins).'''
    exclude = set(exclude) | {'self'}
    if isinstance(obj, type):
        functions = [vars(cls)['__init__'] for cls in obj.__mro__
                     if cls is not object and '__init__' in vars(cls)]
    else:
        functions = [obj]
    fields = {}
    for function in functions:
        try:
            parameters = inspect.signature(function).parameters.values()
        except (TypeError, ValueError):
            continue
        forwards = False
        for param in parameters:
            if param.kind == param.VAR_KEYWORD:
                forwards = True
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD) or \
                    param.name in exclude or param.name in fields:
                continue
            default = MISSING if param.default is param.empty else param.default
            fields[param.name] = Field(param.name, default)

        # parent arguments can only be set by keyword if this class forwards **kwargs
        if not forwards:
            break
    return list(fields.values())


def concrete_subclasses(module: ModuleType, base: type) -> Dict[str, type]:
    '''Returns the non-abstract subclasses of base defined in the given module.'''
    return {name: obj for (name, obj) in vars(module).items()
            if isinstance(obj, type) and issubclass(obj, base) and obj is not base
            and obj.__module__ == module.__name__ and not inspect.isabstract(obj)}


@functools.lru_cache(maxsize=None)
def _parse(module: ModuleType) -> Optional[ast.AST]:
    try:
        return ast.parse(inspect.getsource(module))
    except (OSError, TypeError, SyntaxError):
        return None


def _resolve(expr: ast.AST, module: ModuleType) -> Optional[Callable]:
    parts = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name) or expr.id not in vars(module):
        return None
    obj = vars(module)[expr.id]
    for attr in reversed(parts):
        obj = getattr(obj, attr, None)
    return obj if callable(obj) else None


def trace_kwargs_target(modules: Iterable[ModuleType], kwargs_name: str) -> Optional[Callable]:
    '''Finds the function that a **kwargs dictionary setting is unpacked into, by reading
    the source for calls f(**name), f(**self.name) or f(**self._name) where f is a fixed
    (dotted) name. Returns None when there is no such call, the callee is chosen at run
    time, or different calls disagree.'''
    wanted = kwargs_name.lstrip('_')
    targets = set()
    for module in modules:
        tree = _parse(module)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg is not None:
                    continue
                value = keyword.value
                name = value.attr if isinstance(value, ast.Attribute) else getattr(value, 'id', '')
                if name.lstrip('_') != wanted:
                    continue
                target = _resolve(node.func, module)
                if target is None:
                    return None
                targets.add(target)
    return targets.pop() if len(targets) == 1 else None
