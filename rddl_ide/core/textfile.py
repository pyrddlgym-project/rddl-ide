'''Reads and writes text files, keeping their encoding and line endings, so that saving
a file does not change the bytes the editor did not touch.'''
import codecs
import locale
import os
from typing import NamedTuple, Tuple

NEWLINE_NAMES = {'\r\n': 'CRLF', '\n': 'LF', '\r': 'CR'}


class FileFormat(NamedTuple):
    '''The encoding (a Python codec name) and line ending of a text file.'''
    encoding: str = 'utf-8'
    newline: str = os.linesep
    
    def describe(self) -> Tuple[str, str]:
        '''The names of the encoding and line ending, as shown in the status bar.'''
        if self.encoding == 'utf-8-sig':
            encoding = 'UTF-8 with BOM'
        else:
            encoding = codecs.lookup(self.encoding).name.upper()
        return (encoding, NEWLINE_NAMES[self.newline])


def read(path: str) -> Tuple[str, FileFormat]:
    '''The text of a file, with its line endings as \\n, and the file's format. The file
    is decoded as UTF-8, else in the system's encoding, else as Latin-1.'''
    with open(path, 'rb') as file:
        data = file.read()
    if data.startswith(codecs.BOM_UTF8):
        candidates = ['utf-8-sig']
    else:
        candidates = ['utf-8', locale.getpreferredencoding(False), 'latin-1']
    for encoding in candidates:
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    newline = next((ending for ending in NEWLINE_NAMES if ending in text), os.linesep)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return (text, FileFormat(encoding, newline))


def write(path: str, text: str, file_format: FileFormat) -> FileFormat:
    '''Writes the text in the format, and returns the format written.'''
    text = text.replace('\n', file_format.newline)
    try:
        data = text.encode(file_format.encoding)
    except UnicodeEncodeError:
        file_format = FileFormat('utf-8', file_format.newline)
        data = text.encode(file_format.encoding)
    with open(path, 'wb') as file:
        file.write(data)
    return file_format
