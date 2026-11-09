'''Grounds a domain and instance with pyRDDLGym.'''
import os
import re
import tempfile
from typing import Dict, Iterable, Tuple

IDENTIFIER = re.compile(r'[A-Za-z@](?:[A-Za-z0-9_\-@]*[A-Za-z0-9])?')
FLUENT_SEPARATOR = '___'
OBJECT_SEPARATOR = '__'


def ground(domain: str, instance: str) -> Tuple[str, str]:
    '''The grounded domain and instance of the RDDL texts.'''
    from pyRDDLGym.core.compiler.model import RDDLLiftedModel
    from pyRDDLGym.core.debug.decompiler import RDDLDecompiler
    from pyRDDLGym.core.grounder import RDDLGrounder
    from pyRDDLGym.core.parser.parser import RDDLParser
    from pyRDDLGym.core.parser.reader import RDDLReader

    with tempfile.TemporaryDirectory() as folder:
        paths = [os.path.join(folder, name) for name in ('domain.rddl', 'instance.rddl')]
        for (path, text) in zip(paths, (domain, instance)):
            with open(path, 'w', encoding='utf-8') as file:
                file.write(text)
        text = RDDLReader(*paths).rddltxt
    parser = RDDLParser(lexer=None, verbose=False)
    parser.build()
    model = RDDLLiftedModel(parser.parse(text))
    grounded = RDDLGrounder(model.ast).ground()
    decompiler = RDDLDecompiler()
    return legal_names(decompiler.decompile_domain(grounded),
                       decompiler.decompile_instance(grounded))


def legal_names(*texts: str) -> Tuple[str, ...]:
    '''Renames the grounded variables in the texts, e.g. ADJACENT___f0__f1, whose
    separators pyRDDLGym does not allow in a variable's name.'''
    renames = _renames(
        match.group() for text in texts for match in IDENTIFIER.finditer(text))
    return tuple(IDENTIFIER.sub(
        lambda match: renames.get(match.group(), match.group()), text)
        for text in texts)


def _renames(names: Iterable[str]) -> Dict[str, str]:
    names = set(names)
    taken = {name for name in names if FLUENT_SEPARATOR not in name}
    renames = {}
    for name in sorted(names - taken):
        legal = name.replace(FLUENT_SEPARATOR, '_').replace(OBJECT_SEPARATOR, '_')
        legal = legal.replace('@', '')
        (new, copy) = (legal, 1)
        while new in taken:
            copy += 1
            new = f'{legal}_{copy}'
        taken.add(new)
        renames[name] = new
    return renames
