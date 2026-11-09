'''Where a position is in the structure of a RDDL domain or instance.'''
import re
from typing import List, NamedTuple, Optional

MAX_LENGTH = 40

# comments, identifiers, and any other single character
_TOKEN = re.compile(r"//[^\n]*|[?@]?[A-Za-z][A-Za-z0-9_\-]*'?|\S")
_COMMENT = re.compile(r'//[^\n]*')

# sections whose items are expressions, which pyRDDLGym's messages number from 0
_NUMBERED = {
    'action-preconditions': 'Precondition',
    'state-action-constraints': 'Precondition',
    'state-invariants': 'Invariant',
    'termination': 'Termination',
}
_LISTS = {'requirements'}

# what ends the head of an item, e.g. rlevel'(?r) in rlevel'(?r) = ...;
_HEAD_END = re.compile(r'//[^\n]*|[=:{;}]')


class Crumb(NamedTuple):
    text: str
    offset: int
    

class _Frame:
    '''A part in braces, and the statement in it being read.'''

    def __init__(self, header: Optional[Crumb]):
        self.header = header
        self.statements = 0
        self.end_statement()

    def end_statement(self) -> None:
        self.start = None
        self.head_end = None
        self.first = None
        self.last = None
        

def crumbs(text: str, cursor: int) -> List[Crumb]:
    '''The block, section and item at the offset cursor of the text, as far as they are
    known, e.g. [reservoir_control, cpfs, rlevel'(?r)].'''
    stack = [_Frame(None)]
    for match in _TOKEN.finditer(text):
        token = match.group()
        if match.start() > cursor or (match.start() == cursor and not token[0].isalpha()):
            break
        if token.startswith('//'):
            continue
        frame = stack[-1]
        if token == '}':
            if len(stack) > 1:
                stack.pop()
                if len(stack) == 1:
                    stack[0].end_statement()
            continue
        if token == ';':
            if frame.start is not None:
                frame.statements += 1
            frame.end_statement()
            continue
        if frame.start is None:
            frame.start = match.start()
        if token in ('=', ':', '{') and frame.head_end is None:
            frame.head_end = match.start()
        if token == '{':
            stack.append(_Frame(frame.last))
        elif token[0].isalpha():
            frame.last = Crumb(token, match.start())
            if frame.first is None:
                frame.first = frame.last

    result = []
    if len(stack) < 2:
        if stack[0].last is not None:
            result.append(stack[0].last)
        return result
    (block, section) = (stack[1], stack[2] if len(stack) > 2 else None)
    if block.header is not None:
        result.append(block.header)
    if section is None:
        if block.first is not None:
            result.append(block.first)
        return result
    if section.header is not None:
        result.append(section.header)
        if section.start is not None and section.header.text not in _LISTS:
            result.append(_item(text, cursor, section))
    return result


def _item(text: str, cursor: int, section: _Frame) -> Crumb:
    if section.header.text in _NUMBERED:
        name = f'{_NUMBERED[section.header.text]} {section.statements}'
    else:
        end = section.head_end
        while end is None:
            found = _HEAD_END.search(text, cursor)
            if found is None:
                end = len(text)
            elif found.group().startswith('//'):
                cursor = found.end()
            else:
                end = found.start()
        head = text[section.start:end]
        name = ' '.join(_COMMENT.sub(' ', head).split())
        if len(name) > MAX_LENGTH:
            name = name[:MAX_LENGTH - 1] + '…'
    return Crumb(name, section.start)


def line_column(text: str, offset: int) -> str:
    '''The Tk text index of the offset in the text.'''
    line_start = text.rfind('\n', 0, offset) + 1
    return f'{text.count(chr(10), 0, offset) + 1}.{offset - line_start}'
