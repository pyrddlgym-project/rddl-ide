'''A form that shows every setting of a baseline provider, grouped in collapsible
sections, with class choosers that redraw the settings that depend on them.'''
import sys
import tkinter
from tkinter import BooleanVar, TclError, font

from customtkinter import (
    CTkButton, CTkCheckBox, CTkFont, CTkScrollableFrame, ThemeManager
)

from rddl_ide.core.codearea import monospace_family
from rddl_ide.core.popup import ChoiceMenu
from rddl_ide.core.settings.model import format_value, is_changed, parse_value

CHANGED_COLOR = ('#a06800', '#e5c07b')
FONT_SIZE = 14
WHEEL_STEP = 80  # pixels scrolled per mouse wheel notch before DPI scaling, ~3 rows


class _Entry(tkinter.Entry):
    '''A Tk entry that shows a placeholder while it is empty and does not have the focus.'''

    def __init__(self, master, text, placeholder, text_color, placeholder_color, **kwargs):
        super().__init__(master, fg=text_color, **kwargs)
        self._placeholder = placeholder
        self._colors = (text_color, placeholder_color)
        self._showing = False
        if text:
            self.insert(0, text)
        self.bind('<FocusIn>', self._hide_placeholder, add=True)
        self.bind('<FocusOut>', self._show_placeholder, add=True)
        self._show_placeholder()

    def value(self) -> str:
        return '' if self._showing else self.get()

    def _show_placeholder(self, _=None) -> None:
        if self._placeholder and not self._showing and not self.get():
            self._showing = True
            self.insert(0, self._placeholder)
            self.configure(fg=self._colors[1])

    def _hide_placeholder(self, _=None) -> None:
        if self._showing:
            self._showing = False
            self.delete(0, 'end')
            self.configure(fg=self._colors[0])


class SettingsForm(CTkScrollableFrame):

    def __init__(self, master, provider, state, **kwargs):
        palette = ThemeManager.theme['Palette']
        super().__init__(master, corner_radius=0, fg_color=palette['content'], **kwargs)
        self.provider = provider
        self.state = state
        self.open_sections = {provider.sections()[0].id}
        self.only_changed = BooleanVar(value=False)
        self.family = monospace_family()
        self.columnconfigure(0, weight=1)
        self.render()

    def _mouse_wheel_all(self, event):
        if not sys.platform.startswith('win') or self._shift_pressed or \
                not self._check_if_valid_scroll(event.widget):
            return super()._mouse_wheel_all(event)
        if self._parent_canvas.yview() != (0.0, 1.0):
            pixels = round(event.delta / 120 * self._scaled(WHEEL_STEP))
            if pixels == 0:
                pixels = 1 if event.delta > 0 else -1
            self._parent_canvas.yview('scroll', -pixels, 'units')

    # ===========================================================================
    # drawing
    # ===========================================================================

    def _scaled(self, value: int) -> int:
        return round(value * self._get_widget_scaling())

    def _theme(self) -> None:
        '''Resolves the theme colors and the font for the current appearance and scaling.'''
        color = self._apply_appearance_mode
        entry = ThemeManager.theme['CTkEntry']
        self.mono = font.Font(family=self.family, size=-self._scaled(FONT_SIZE))
        self.background = tkinter.Frame.cget(self, 'bg')
        self.label_color = color(ThemeManager.theme['CTkLabel']['text_color'])
        self.changed_color = color(CHANGED_COLOR)
        self.entry_style = dict(
            bg=color(entry['fg_color']), insertbackground=color(entry['text_color']),
            relief='flat', bd=self._scaled(3), highlightthickness=1,
            highlightbackground=color(entry['border_color']),
            highlightcolor=color(ThemeManager.theme['CTkButton']['fg_color']))
        self.entry_colors = (color(entry['text_color']), color(entry['placeholder_text_color']))

    def render(self) -> None:
        self._theme()
        content = tkinter.Frame(self, bg=self.background)
        content.columnconfigure(0, weight=1)
        self._render_into(content)
        for widget in self.winfo_children():
            if widget is not content:
                widget.destroy()
        content.grid(row=0, column=0, sticky='nsew')

    def _render_into(self, content) -> None:
        CTkCheckBox(content, text='show changed only', variable=self.only_changed,
                    command=self.render).grid(row=0, column=0, sticky='w', padx=8, pady=6)
        row = 1
        for section in self.provider.sections():
            option = section.option(self.state)
            fields = section.fields(option, self.state)
            is_open = section.id in self.open_sections
            arrow = '▾' if is_open else '▸'
            CTkButton(content, text=f'{arrow}  {section.title}    ({len(fields)} settings)',
                      anchor='w', corner_radius=4, fg_color='transparent',
                      hover_color=ThemeManager.theme['Palette']['hover'],
                      text_color=ThemeManager.theme['Palette']['text'],
                      font=CTkFont(weight='bold'),
                      command=lambda s=section.id: self.toggle(s)
                      ).grid(row=row, column=0, sticky='ew', padx=4, pady=(4, 0))
            row += 1
            if is_open:
                body = tkinter.Frame(content, bg=self.background)
                body.grid(row=row, column=0, sticky='ew',
                          padx=(self._scaled(16), self._scaled(4)),
                          pady=(self._scaled(2), self._scaled(4)))
                body.columnconfigure(1, weight=1)
                self._render_section(body, section, option, fields)
                row += 1

    def _render_section(self, body, section, option, fields) -> None:
        row = 0
        if section.chooser is not None:
            self._name_label(body, row, section.chooser, False)
            menu = ChoiceMenu(body, values=section.options(self.state),
                                 command=lambda value, s=section: self.choose(s, value))
            menu.set(option)
            menu.grid(row=row, column=1, sticky='w', pady=1)
            row += 1
        for field in fields:
            if field.nested is None:
                row = self._row(body, row, section, option, field.name, field)
                continue
            changed = [is_changed(self.state.text(
                            section.id, option, f'{field.name}.{s.name}'), s)
                       for s in field.nested]
            if self.only_changed.get() and not any(changed):
                continue
            self._name_label(body, row, field.name, any(changed))
            row += 1
            for sub in field.nested:
                row = self._row(
                    body, row, section, option, f'{field.name}.{sub.name}', sub, indent='    ')
        self._extra_row(body, row, section)

    def _name_label(self, body, row, text, changed) -> tkinter.Label:
        label = tkinter.Label(body, text=text, font=self.mono, anchor='w', bg=self.background,
                              fg=self.changed_color if changed else self.label_color)
        label.grid(row=row, column=0, sticky='w', padx=(0, self._scaled(12)), pady=1)
        return label

    def _color(self, label, changed) -> None:
        try:
            label.configure(fg=self.changed_color if changed else self.label_color)
        except TclError:  
            pass

    def _entry(self, body, row, text, placeholder) -> _Entry:
        entry = _Entry(body, text, placeholder, *self.entry_colors, font=self.mono,
                       **self.entry_style)
        entry.grid(row=row, column=1, sticky='ew', pady=1)
        return entry

    def _row(self, body, row, section, option, path, field, indent='') -> int:
        text = self.state.text(section.id, option, path)
        changed = is_changed(text, field)
        if self.only_changed.get() and not changed:
            return row
        shown = format_value(field.default) if text is None else text
        name = indent + field.name.split('.')[-1] + (' *' if field.required else '')
        label = self._name_label(body, row, name, changed)

        def edited(value):
            self.state.set_text(section.id, option, path, value)
            self._color(label, is_changed(value, field))

        if field.options is not None:
            def picked(value):  # other fields can depend on the choice, so redraw
                self.state.set_text(section.id, option, path, value)
                self.render()

            menu = ChoiceMenu(body, values=field.options, command=picked)
            menu.set(shown)
            menu.grid(row=row, column=1, sticky='w', pady=1)

        elif isinstance(field.default, bool):
            style = {k: v for (k, v) in self.entry_style.items() if k != 'insertbackground'}
            toggle = tkinter.Label(body, text=str(parse_value(shown) is True), width=6,
                                   anchor='w', font=self.mono, fg=self.entry_colors[0],
                                   cursor='hand2', takefocus=True, **style)

            def toggled(_):
                value = str(toggle.cget('text') != 'True')
                toggle.configure(text=value)
                edited(value)

            for event in ('<Button-1>', '<space>'):
                toggle.bind(event, toggled)
            toggle.bind('<Button-1>', lambda _: toggle.focus_set(), add=True)
            toggle.grid(row=row, column=1, sticky='w', pady=1)
            
        else:
            entry = self._entry(body, row, shown, 'required' if field.required else None)
            for event in ('<KeyRelease>', '<FocusOut>'):
                entry.bind(event, lambda _: edited(entry.value()), add=True)
        return row + 1

    def _extra_row(self, body, row, section) -> None:
        text = self.state.extra(section.id)
        if self.only_changed.get() and not text.strip():
            return
        label = self._name_label(body, row, 'additional settings', bool(text.strip()))
        entry = self._entry(body, row, text, "{'name': value, ...}")

        def edited(_):
            self.state.set_extra(section.id, entry.value())
            self._color(label, bool(entry.value().strip()))

        for event in ('<KeyRelease>', '<FocusOut>'):
            entry.bind(event, edited, add=True)

    # ===========================================================================
    # appearance: the plain Tk rows take their colors and font size when drawn
    # ===========================================================================

    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        self.render()

    def _set_scaling(self, new_widget_scaling, new_window_scaling):
        super()._set_scaling(new_widget_scaling, new_window_scaling)
        self.render()

    # ===========================================================================
    # events
    # ===========================================================================

    def choose(self, section, option) -> None:
        section.choose(self.state, option)
        self.render()

    def toggle(self, section_id) -> None:
        self.open_sections ^= {section_id}
        self.render()
