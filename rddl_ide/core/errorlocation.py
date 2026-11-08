'''Finds the part of the domain or instance source that a pyRDDLGym error points to.

A syntax error shows the line at fault among the lines around it. Its line number is
not used: it counts lines of the text the parser read, which is the domain and the
instance after preprocessing (comments and blank lines removed, macros expanded, ...),
not lines of the editors. Instead the shown lines are matched to the sources' lines,
so a line that occurs several times (e.g. '};') is found by its neighbours.

A compiler error quotes the decompiled expression at fault and the definition it is in
(e.g. a CPF), so the expression is searched for in that definition, ignoring
differences in whitespace.'''
import re
from difflib import SequenceMatcher
from typing import List, NamedTuple, Optional, Tuple

_ANSI_CODE = re.compile(r'\033\[[0-9;]*m')
_SYNTAX_LINE = re.compile(r'\033\[4m(.*?)\033\[(?:24|0)m')
_SYNTAX_MARK = ' >> '  # how the message marks the line at fault among the lines shown
_ROOT = 'Please check expression for '
_COMMENT = re.compile(r'//[^\n]*')

# below this similarity a fuzzy match is more likely misleading than helpful
MIN_SIMILARITY = 0.6

# blocks whose statements compiler errors number, e.g. 'Precondition 2'
_NUMBERED_BLOCKS = {
    'Invariant': ('state-invariants',),
    'Precondition': ('action-preconditions', 'state-action-constraints'),
    'Termination': ('termination',),
}


class Location(NamedTuple):
    source: str  # 'domain' or 'instance'
    start: str   # Tk text indices, 'line.column'
    end: str


def locate_error(message: str, domain: str, instance: str) -> Optional[Location]:
    '''Returns where in the domain or instance text the error message points to, or
    None if it does not point to any source.'''
    sources = [('domain', domain), ('instance', instance)]
    line = _SYNTAX_LINE.search(message)
    if line is not None:
        (shown, at_fault) = _shown_lines(message, line.group(1))
        return _locate_line(shown, at_fault, sources) or \
            _locate_expression(line.group(1), None, sources)
    message = _ANSI_CODE.sub('', message)
    if '>>' not in message:
        return None
    expression = message[message.index('>>') + len('>>'):]
    root = None
    if _ROOT in expression:
        (expression, root) = expression.split(_ROOT, 1)
        root = root.strip().rstrip('.')
    return _locate_expression(expression, root, sources)


def _index(text: str, offset: int) -> str:
    line = text.count('\n', 0, offset) + 1
    column = offset - (text.rfind('\n', 0, offset) + 1)
    return f'{line}.{column}'


def _blank_comments(text: str) -> str:
    '''Replaces comments by spaces, so that offsets stay the same.'''
    return _COMMENT.sub(lambda match: ' ' * len(match.group()), text)


# ===========================================================================
# syntax errors
# ===========================================================================

def _shown_lines(message: str, at_fault: str) -> Tuple[List[str], int]:
    '''Returns the lines a syntax error message shows, stripped, and the position of the
    line at fault among them; just that line if the message shows no others.'''
    shown, position = [], None
    for line in _ANSI_CODE.sub('', message).split('\n'):
        if line.startswith(_SYNTAX_MARK):
            position = len(shown)
            shown.append(line[len(_SYNTAX_MARK):].strip())
        elif line.startswith(' ' * len(_SYNTAX_MARK)):
            if line.strip():  # like the sources' blank lines, which the parser skips
                shown.append(line.strip())
        elif position is not None:  # the end of the lines shown
            break
        else:  # a line before the ones shown
            shown = []
    if position is None or shown[position] != at_fault.strip():
        return [at_fault.strip()], 0
    return shown, position


def _locate_line(shown: List[str], at_fault: int, sources) -> Optional[Location]:
    '''Finds the source line at fault: of the lines that read like it, the one whose
    neighbours read most like the lines shown around it (the first one on a tie). The
    parser reads the sources' lines without comments and blank lines.'''
    lines = []  # (source name, source text, start, end, content) of each line read
    for (name, text) in sources:
        offset = 0
        for line in text.split('\n'):  # Tk, like the parser, only breaks lines at \n
            content = _blank_comments(line).strip()
            if content:
                start = offset + len(line) - len(line.lstrip())
                end = offset + len(_blank_comments(line).rstrip())
                lines.append((name, text, start, end, content))
            offset += len(line) + 1

    def agreement(k):  # how many shown lines the lines around line k read like
        return sum(1 for (j, wanted) in enumerate(shown)
                   if 0 <= k - at_fault + j < len(lines)
                   and lines[k - at_fault + j][4] == wanted)

    candidates = [k for (k, line) in enumerate(lines) if line[4] == shown[at_fault]]
    if not candidates:
        return None
    (name, text, start, end, _) = lines[max(candidates, key=agreement)]
    return Location(name, _index(text, start), _index(text, end))


# ===========================================================================
# compiler errors
# ===========================================================================

def _statement_end(text: str, start: int) -> int:
    '''Returns the offset of the ; that ends the statement starting at start.'''
    depth = 0
    for i in range(start, len(text)):
        if text[i] in '([{':
            depth += 1
        elif text[i] in ')]}':
            if depth == 0:  # the block ended without a ;
                return i
            depth -= 1
        elif text[i] == ';' and depth == 0:
            return i
    return len(text)


def _scope(text: str, root: Optional[str]) -> Optional[Tuple[int, int]]:
    '''Returns the span of the definition an error names, e.g. 'CPF <burning'>',
    'reward' or 'Precondition 2', in text whose comments are blanked.'''
    if root is None:
        return None
    match = re.fullmatch(r'(?:policy )?CPF <?(.+?)>?', root)
    if match is not None or root == 'reward':
        name = 'reward' if match is None else match.group(1)
        head = re.compile(r'[;{]\s*(' + re.escape(name) + r')\s*(?:\([^)]*\))?\s*=(?!=)')
        found = head.search(text)
        return None if found is None else (found.start(1), _statement_end(text, found.start(1)))
    match = re.fullmatch(r'(\w+) (\d+)', root)
    if match is None or match.group(1) not in _NUMBERED_BLOCKS:
        return None
    for keyword in _NUMBERED_BLOCKS[match.group(1)]:
        block = re.search(r'(?<![\w-])' + re.escape(keyword) + r'\s*\{', text)
        if block is None:
            continue
        start = block.end()
        for _ in range(int(match.group(2)) - 1):
            start = _statement_end(text, start) + 1
        start += len(text[start:]) - len(text[start:].lstrip())
        end = _statement_end(text, start)
        return (start, end) if start < end else None
    return None


def _closest(text: str, span: Tuple[int, int], query: str) -> Optional[Tuple[float, int, int]]:
    '''Finds the part of text[span] most similar to query, ignoring whitespace (the
    decompiler formats expressions differently from the source). Returns the similarity
    and the offsets of that part.'''
    keep = [i for i in range(*span) if not text[i].isspace()]
    corpus = ''.join(text[i] for i in keep)
    query = ''.join(query.split())
    if not corpus or not query:
        return None
    exact = corpus.find(query)
    if exact >= 0:
        return 1.0, keep[exact], keep[exact + len(query) - 1] + 1

    # coarse scan of windows of the query's length, then refine both ends
    matcher = SequenceMatcher(None, autojunk=False)
    matcher.set_seq2(query)

    def similarity(window):
        (a, b) = window
        matcher.set_seq1(corpus[a:b])
        return matcher.ratio()

    width = min(len(query), len(corpus))
    step = max(1, width // 8)
    starts = list(range(0, len(corpus) - width + 1, step)) + [len(corpus) - width]
    best = max(((a, a + width) for a in starts), key=similarity)
    for end_moves in (False, True):
        (a, b) = best
        moves = [(a, b + d) if end_moves else (a + d, b) for d in range(-step, step + 1)]
        moves = [(x, y) for (x, y) in moves if 0 <= x < y <= len(corpus)]
        best = max(moves, key=similarity)
    (a, b) = best
    return similarity(best), keep[a], keep[b - 1] + 1


def _locate_expression(expression: str, root: Optional[str], sources) -> Optional[Location]:
    '''Finds the expression in the definition named by root if that can be found, else
    anywhere in the sources.'''
    results: List[Tuple[float, str, str, int, int]] = []
    for (name, text) in sources:
        blanked = _blank_comments(text)
        span = _scope(blanked, root)
        found = _closest(blanked, span or (0, len(blanked)), expression)
        if span is not None:  # the definition is in this source: look nowhere else
            results = []
        if found is not None:
            results.append((found[0], name, text, found[1], found[2]))
        if span is not None:
            break
    if not results:
        return None
    (similarity, name, text, start, end) = max(results, key=lambda result: result[0])
    if similarity < MIN_SIMILARITY:
        return None
    return Location(name, _index(text, start), _index(text, end))
