'''A form that shows every setting of a baseline provider, grouped in collapsible
sections, with class choosers that redraw the settings that depend on them.'''
from tkinter import BooleanVar, TclError, font

from customtkinter import (
    CTkButton, CTkCheckBox, CTkEntry, CTkFont, CTkFrame, CTkLabel, CTkOptionMenu,
    CTkScrollableFrame, ThemeManager
)

from rddl_ide.core.settings.model import format_value, is_changed, parse_value

CHANGED_COLOR = ('#a06800', '#e5c07b')


class SettingsForm(CTkScrollableFrame):

    def __init__(self, master, provider, state, **kwargs):
        super().__init__(master, corner_radius=0, **kwargs)
        self.provider = provider
        self.state = state
        self.open_sections = {provider.sections()[0].id}
        self.only_changed = BooleanVar(value=False)
        family = 'Consolas' if 'Consolas' in font.families() else 'Courier'
        self.mono = CTkFont(family=family, size=14)
        self.label_color = ThemeManager.theme['CTkLabel']['text_color']
        self.columnconfigure(0, weight=1)
        self.render()

    # ===========================================================================
    # drawing
    # ===========================================================================

    def render(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()
        CTkCheckBox(self, text='show changed only', variable=self.only_changed,
                    command=self.render).grid(row=0, column=0, sticky='w', padx=8, pady=6)
        row = 1
        for section in self.provider.sections():
            if not section.visible(self.state):
                continue
            option = section.option(self.state)
            fields = section.fields(option, self.state)
            is_open = section.id in self.open_sections
            arrow = '▾' if is_open else '▸'
            CTkButton(self, text=f'{arrow}  {section.title}    ({len(fields)} settings)',
                      anchor='w', corner_radius=0, fg_color=('gray81', 'gray20'),
                      hover_color=('gray75', 'gray25'), text_color=self.label_color,
                      command=lambda s=section.id: self.toggle(s)
                      ).grid(row=row, column=0, sticky='ew', pady=(4, 0))
            row += 1
            if is_open:
                body = CTkFrame(self, fg_color='transparent')
                body.grid(row=row, column=0, sticky='ew', padx=(16, 4), pady=(2, 4))
                body.columnconfigure(1, weight=1)
                self._render_section(body, section, option, fields)
                row += 1

    def _render_section(self, body, section, option, fields) -> None:
        row = 0
        if section.chooser is not None:
            self._name_label(body, row, section.chooser, False)
            menu = CTkOptionMenu(body, values=section.options(self.state),
                                 command=lambda value, s=section: self.choose(s, value))
            menu.set(option)
            menu.grid(row=row, column=1, sticky='w', pady=1)
            row += 1
        for field in fields:
            if field.nested is None:
                row = self._row(body, row, section, option, field.name, field)
                continue
            changed = [is_changed(self.state.text(section.id, option, f'{field.name}.{s.name}'), s)
                       for s in field.nested]
            if self.only_changed.get() and not any(changed):
                continue
            self._name_label(body, row, field.name, any(changed))
            row += 1
            for sub in field.nested:
                row = self._row(body, row, section, option, f'{field.name}.{sub.name}', sub,
                                indent='    ')
        self._extra_row(body, row, section)

    def _name_label(self, body, row, text, changed) -> CTkLabel:
        label = CTkLabel(body, text=text, font=self.mono, anchor='w',
                         text_color=CHANGED_COLOR if changed else self.label_color)
        label.grid(row=row, column=0, sticky='w', padx=(0, 12))
        return label

    def _color(self, label, changed) -> None:
        try:
            label.configure(text_color=CHANGED_COLOR if changed else self.label_color)
        except TclError:  # the form was redrawn while the entry still had the focus
            pass

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

        if isinstance(field.default, bool):
            variable = BooleanVar(value=parse_value(shown) is True)
            CTkCheckBox(body, text='', variable=variable,
                        command=lambda: edited(str(variable.get()))
                        ).grid(row=row, column=1, sticky='w', pady=1)
        else:
            entry = CTkEntry(body, font=self.mono,
                             placeholder_text='required' if field.required else None)
            if shown:
                entry.insert(0, shown)
            for event in ('<KeyRelease>', '<FocusOut>'):
                entry.bind(event, lambda _: edited(entry.get()))
            entry.grid(row=row, column=1, sticky='ew', pady=1)
        return row + 1

    def _extra_row(self, body, row, section) -> None:
        text = self.state.extra(section.id)
        if self.only_changed.get() and not text.strip():
            return
        label = self._name_label(body, row, 'additional settings', bool(text.strip()))
        entry = CTkEntry(body, font=self.mono, placeholder_text="{'name': value, ...}")
        if text:
            entry.insert(0, text)

        def edited(_):
            self.state.set_extra(section.id, entry.get())
            self._color(label, bool(entry.get().strip()))

        for event in ('<KeyRelease>', '<FocusOut>'):
            entry.bind(event, edited)
        entry.grid(row=row, column=1, sticky='ew', pady=1)

    # ===========================================================================
    # events
    # ===========================================================================

    def choose(self, section, option) -> None:
        section.choose(self.state, option)
        self.render()

    def toggle(self, section_id) -> None:
        self.open_sections ^= {section_id}
        self.render()
