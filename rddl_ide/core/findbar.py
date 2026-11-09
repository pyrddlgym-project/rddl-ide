'''A bar above a code viewer to find text in it, and replace it.'''
import re
from tkinter import TclError
from typing import List, Tuple

from customtkinter import (
    AppearanceModeTracker, CTkButton, CTkEntry, CTkFont, CTkFrame, CTkLabel, ThemeManager
)

from rddl_ide.core.icons import IconButton

ENTRY_WIDTH = 260
MATCH_TAG = 'find_match'
CURRENT_TAG = 'find_current'
MATCH_COLORS = ('#FCEBA6', '#4B4321')
CURRENT_COLORS = ('#F5C451', '#8A6D1F')
MAX_MATCHES = 10000


class FindBar(CTkFrame):
    '''Finds the text typed in the viewer as it is typed, highlighting all matches, and
    selects the next or previous one (Enter, Shift+Enter).'''

    def __init__(self, viewer, before):
        palette = ThemeManager.theme['Palette']
        super().__init__(viewer.master, corner_radius=0, fg_color=palette['chrome'])
        self.viewer = viewer
        self._before = before
        self.match_case = False
        self.matches: List[Tuple[str, str]] = []
        self._searched = None
        font = CTkFont(size=13)

        find_row = CTkFrame(self, fg_color='transparent')
        find_row.pack(side='top', fill='x', padx=8, pady=(6, 3))
        self.find_entry = CTkEntry(
            find_row, width=ENTRY_WIDTH, height=28, placeholder_text='Find', font=font)
        self.find_entry.pack(side='left')
        self.case_button = CTkButton(
            find_row, text='Aa', width=28, height=28, corner_radius=4,
            fg_color='transparent', hover_color=palette['hover'],
            text_color=palette['text'], font=font, command=self.toggle_case)
        self.case_button.pack(side='left', padx=(4, 0))
        self.count = CTkLabel(find_row, text='', width=90, anchor='w', font=font,
                              text_color=palette['text_muted'])
        self.count.pack(side='left', padx=(8, 0))
        IconButton(find_row, 'up', 'Previous match (Shift+Enter)', lambda: self.step(-1)
                   ).pack(side='left')
        IconButton(find_row, 'down', 'Next match (Enter)', lambda: self.step(1)
                   ).pack(side='left')
        IconButton(find_row, 'close', 'Close (Escape)', self.hide).pack(side='right')

        self.replace_row = CTkFrame(self, fg_color='transparent')
        self.replace_entry = CTkEntry(self.replace_row, width=ENTRY_WIDTH, height=28,
                                      placeholder_text='Replace', font=font)
        self.replace_entry.pack(side='left')
        for (text, command) in (('Replace', self.replace), 
                                ('Replace All', self.replace_all)):
            CTkButton(self.replace_row, text=text, width=0, height=28, font=font,
                      command=command).pack(side='left', padx=(6, 0))
        CTkFrame(self, height=1, corner_radius=0, fg_color=palette['border']).pack(
            side='bottom', fill='x')

        self.find_entry.bind('<KeyRelease>', self._typed)
        self.find_entry.bind('<Return>', lambda _: self.step(1))
        self.find_entry.bind('<Shift-Return>', lambda _: self.step(-1))
        self.replace_entry.bind('<Return>', lambda _: self.replace())
        for entry in (self.find_entry, self.replace_entry):
            entry.bind('<Escape>', lambda _: self.hide())
        self._color_tags()
        AppearanceModeTracker.add(self._recolor, self)
        self.bind('<Destroy>', 
                  lambda event: event.widget is self and
                    AppearanceModeTracker.remove(self._recolor), add='+')

    # ===========================================================================
    # showing
    # ===========================================================================

    def show(self, replace: bool=False) -> None:
        '''Shows the bar, with the replace row if replace, to find the text selected in
        the viewer (if any, on one line) or else the text last searched.'''
        if not self.winfo_ismapped():
            self.pack(side='top', fill='x', before=self._before)
        if replace:
            self.replace_row.pack(side='top', fill='x', padx=8, pady=(0, 6))
        else:
            self.replace_row.pack_forget()
        selected = self._selected_text()
        if selected and '\n' not in selected:
            self.find_entry.delete(0, 'end')
            self.find_entry.insert(0, selected)
        entry = self.replace_entry if replace and self.find_entry.get() else self.find_entry
        entry.focus_set()
        entry.select_range(0, 'end')
        self.search()

    def hide(self) -> None:
        self.viewer.tag_remove(MATCH_TAG, '1.0', 'end')
        self.viewer.tag_remove(CURRENT_TAG, '1.0', 'end')
        self.pack_forget()
        self.viewer.focus_set()

    def toggle_case(self) -> None:
        self.match_case = not self.match_case
        palette = ThemeManager.theme['Palette']
        self.case_button.configure(
            fg_color=palette['hover'] if self.match_case else 'transparent')
        self.search()

    # ===========================================================================
    # finding
    # ===========================================================================

    def _typed(self, event) -> None:
        if event.keysym not in ('Return', 'Escape', 'Shift_L', 'Shift_R'):
            self.search()

    def search(self) -> None:
        '''Highlights all the matches, and selects the first after the cursor.'''
        self._find_all()
        viewer = self.viewer
        self._select(self._first_from(
            viewer.index('sel.first') if viewer.tag_ranges('sel') else 
            viewer.index('insert')))

    def _find_all(self) -> None:
        '''Finds and highlights all the matches.'''
        viewer = self.viewer
        viewer.tag_remove(MATCH_TAG, '1.0', 'end')
        viewer.tag_remove(CURRENT_TAG, '1.0', 'end')
        query = self.find_entry.get()
        text = viewer.content()
        self._searched = (text, query, self.match_case)
        self.matches = []
        if query:
            flags = 0 if self.match_case else re.IGNORECASE
            for (k, found) in enumerate(re.finditer(re.escape(query), text, flags)):
                if k == MAX_MATCHES:
                    break
                self.matches.append(
                    (f'1.0 + {found.start()} chars', f'1.0 + {found.end()} chars'))
            self.matches = [(viewer.index(start), viewer.index(end))
                            for (start, end) in self.matches]
            for (start, end) in self.matches:
                viewer.tag_add(MATCH_TAG, start, end)

    def _refresh(self) -> None:
        '''Finds the matches again if the text was edited since they were found.'''
        if self._searched != (
                self.viewer.content(), self.find_entry.get(), self.match_case):
            self._find_all()

    def _first_from(self, index: str):
        '''The match starting at or after the index, else the first match.'''
        for (k, (start, _)) in enumerate(self.matches):
            if self.viewer.compare(start, '>=', index):
                return k
        return 0 if self.matches else None

    def step(self, direction: int) -> None:
        '''Selects the next (1) or previous (-1) match.'''
        self._refresh()
        if not self.matches:
            self.search()
            return
        current = self._current()
        if current is None:
            k = self._first_from(self.viewer.index('insert'))
            if direction < 0:
                k = (k - 1) % len(self.matches)
        else:
            k = (current + direction) % len(self.matches)
        self._select(k)

    def _current(self):
        '''The match that is selected, if any.'''
        viewer = self.viewer
        if not viewer.tag_ranges('sel'):
            return None
        selected = (viewer.index('sel.first'), viewer.index('sel.last'))
        return next(
            (k for (k, match) in enumerate(self.matches) if match == selected), None)

    def _select(self, k) -> None:
        viewer = self.viewer
        viewer.tag_remove(CURRENT_TAG, '1.0', 'end')
        if k is None:
            self.count.configure(text='No results' if self.find_entry.get() else '')
            return
        (start, end) = self.matches[k]
        viewer.tag_remove('sel', '1.0', 'end')
        viewer.tag_add('sel', start, end)
        viewer.tag_add(CURRENT_TAG, start, end)
        viewer.mark_set('insert', end)
        viewer.see(start)
        total = f'{len(self.matches)}+' if len(self.matches) == MAX_MATCHES else \
            len(self.matches)
        self.count.configure(text=f'{k + 1} of {total}')

    def _selected_text(self) -> str:
        try:
            return self.viewer.get('sel.first', 'sel.last')
        except TclError:
            return ''

    # ===========================================================================
    # replacing
    # ===========================================================================

    def replace(self) -> None:
        '''Replaces the selected match, and selects the next one.'''
        self._refresh()
        current = self._current()
        if current is None:
            self.step(1)
            return
        (start, end) = self.matches[current]
        viewer = self.viewer
        viewer.edit_separator()
        viewer.delete(start, end)
        viewer.insert(start, self.replace_entry.get())
        viewer.edit_separator()
        viewer.apply()
        viewer.mark_set('insert', f'{start} + {len(self.replace_entry.get())} chars')
        viewer.tag_remove('sel', '1.0', 'end')
        self.search()

    def replace_all(self) -> None:
        '''Replaces all the matches, in one step that undo takes back.'''
        query = self.find_entry.get()
        if not query:
            return
        viewer = self.viewer
        text = viewer.content()
        flags = 0 if self.match_case else re.IGNORECASE
        replacement = self.replace_entry.get()
        (new_text, count) = re.subn(
            re.escape(query), lambda _: replacement, text, flags=flags)
        if count:
            cursor = viewer.index('insert')
            viewer.replace_text(new_text)
            viewer.mark_set('insert', cursor)
            viewer.see('insert')
        self.search()
        self.count.configure(text=f'Replaced {count}')

    # ===========================================================================
    # colors
    # ===========================================================================

    def _color_tags(self) -> None:
        viewer = self.viewer
        viewer.tag_config(
            MATCH_TAG, background=viewer._apply_appearance_mode(MATCH_COLORS))
        viewer.tag_config(
            CURRENT_TAG, background=viewer._apply_appearance_mode(CURRENT_COLORS))
        viewer.tag_raise(CURRENT_TAG, MATCH_TAG)
        viewer.tag_lower(MATCH_TAG, 'sel')

    def _recolor(self, *_) -> None:
        self.after_idle(self._color_tags)
