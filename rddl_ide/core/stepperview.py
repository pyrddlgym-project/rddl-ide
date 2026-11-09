'''A window that runs an episode of the policy one step at a time, showing the state,
the action taken, the intermediate fluents and the picture of the visualizer.'''
import sys
import tkinter
import traceback
from tkinter import TclError, messagebox, ttk
from typing import Callable, List, Optional, Tuple

from customtkinter import (
    AppearanceModeTracker, CTkEntry, CTkFont, CTkFrame, CTkImage, CTkLabel, CTkScrollbar,
    CTkToplevel, ScalingTracker, ThemeManager
)

from rddl_ide.core.appicon import set_icon
from rddl_ide.core.errorlocation import strip_ansi
from rddl_ide.core.graphview import _mix
from rddl_ide.core.icons import IconButton
from rddl_ide.core.shortcuts import label
from rddl_ide.core.statusbar import RunStopped, StatusLine, number
from rddl_ide.core.stepping import Snapshot, Stepper
from rddl_ide.core.titlebar import match_title_bar

FONT_SIZE = 13
ROW_HEIGHT = 24
VALUE_WIDTH = 160
SIZE = (1100, 680)
STYLE = 'Stepper.Treeview'
HIGHLIGHT_TINT = 0.22

STEP = label('F10')
RUN = label('F5')
STOP = label('F5', shift=True)
HINT = f'{STEP} step  ·  {RUN} run to the end  ·  {STOP} stop  ·  ' \
       f'highlighted: changed by the last step (actions: not the default)'


def _format(value) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float):
        return number(value)
    return str(value)


class StepperWindow(CTkToplevel):
    '''Steps through an episode of the stepper's policy. progress is that the policy
    reports its planning to; busy(True or False) is called as steps start and end, and
    allowed() says whether a step may start (e.g. not while another run is going);
    on_error(message) is called with the error a step raised, and on_close(note) when
    the window is closed, with what became of the simulation log.'''

    def __init__(self, master, stepper: Stepper, progress, title: str,
                 busy: Callable[[bool], None], allowed: Callable[[], bool],
                 on_error: Callable[[str], None], on_close: Callable[[str], None]):
        palette = ThemeManager.theme['Palette']
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.after(250, lambda: set_icon(self))
        match_title_bar(self)
        self.stepper = stepper
        self.progress = progress
        progress.bar = self
        progress.note_text = progress.episode_text = progress.training_text = ''
        self._busy_changed = busy
        self._allowed = allowed
        self._on_error = on_error
        self._on_close = on_close
        self._stepping = False
        self._running = False
        self._closing = False
        self._closed_iids = set()
        self._rows: List[Tuple[str, str, str, str, Tuple[str, ...]]] = []
        self._picture: Optional[CTkImage] = None
        text_font = CTkFont(size=FONT_SIZE)

        # toolbar: the controls, the step, and a filter
        bar = CTkFrame(self, corner_radius=0, fg_color=palette['chrome'])
        bar.pack(side='top', fill='x')
        CTkFrame(bar, height=1, corner_radius=0, fg_color=palette['border']).pack(
            side='bottom', fill='x')
        self.buttons = {}
        for (name, icon, tooltip, command) in (
                ('step', 'step', f'Step ({STEP})', self.step),
                ('run', 'run_to_end', f'Run to the end ({RUN})', self.run_to_end),
                ('stop', 'stop', f'Stop ({STOP})', self.stop),
                ('restart', 'restart', 'Restart the episode', self.restart)):
            self.buttons[name] = IconButton(bar, icon, tooltip, command)
            self.buttons[name].pack(
                side='left', padx=(4 if name == 'step' else 0, 0), pady=4)
        self.status = CTkLabel(
            bar, text='', anchor='w', font=text_font, text_color=palette['text'])
        self.status.pack(side='left', padx=(12, 0))
        self.filter = CTkEntry(
            bar, width=220, height=28, font=text_font, placeholder_text='Filter fluents')
        self.filter.pack(side='right', padx=8)
        self.filter.bind('<KeyRelease>', lambda _: self._show_rows(), add=True)

        self.footer = StatusLine(self, HINT)
        self.footer.pack(side='bottom', fill='x')

        # the values on the left, the picture on the right
        divider = self._apply_appearance_mode(ThemeManager.theme['CTk']['fg_color'])
        self.panes = tkinter.PanedWindow(
            self, orient='horizontal', sashwidth=6, bd=0, bg=divider)
        self.panes.pack(fill='both', expand=True)
        table = CTkFrame(self.panes, corner_radius=0, fg_color=palette['content'])
        self.tree = ttk.Treeview(
            table, style=STYLE, columns=('value',), selectmode='browse')
        self.tree.heading('#0', text='Fluent', anchor='w')
        self.tree.heading('value', text='Value', anchor='w')
        scrollbar = CTkScrollbar(table, orientation='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<<TreeviewOpen>>', lambda _: self._opened(True))
        self.tree.bind('<<TreeviewClose>>', lambda _: self._opened(False))
        self.panes.add(table, minsize=300, stretch='always')
        self.picture = None
        if stepper.render:
            self.picture = CTkLabel(self.panes, text='', fg_color=palette['content'])
            self.panes.add(self.picture, minsize=200, stretch='always')
            self.picture.bind('<Configure>', lambda _: self._schedule_picture(), add=True)
        self._picture_pending = None

        for (sequence, command) in (('<KeyPress-F10>', self.step),
                                    ('<KeyPress-F5>', self.run_to_end),
                                    ('<Shift-KeyPress-F5>', self.stop)):
            self.bind(sequence, lambda _, command=command: (command(), 'break')[1])
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Destroy>', lambda e: e.widget is self and self._closed(), add='+')
        AppearanceModeTracker.add(self._recolor, self)
        self._style()
        self._place()
        self._update_buttons()
        self.after(10, self.restart)

    # ===========================================================================
    # controls
    # ===========================================================================

    def step(self) -> None:
        if self._can_step() and not self._running:
            self._run(self.stepper.step)

    def run_to_end(self) -> None:
        '''Steps until the episode ends or Stop is pressed, showing each step.'''
        if not self._can_step() or self._running:
            return
        self._running = True
        self._update_buttons()

        def next_step():
            if self._running and not self.stepper.done and \
                    self._run(self.stepper.step) is not None:
                self.after(1, next_step)
            else:
                self._running = False
                self._update_buttons()
        next_step()

    def stop(self) -> None:
        self._running = False
        if self._stepping:
            self.progress.stop()
        self._update_buttons()

    def restart(self) -> None:
        if not self._stepping and not self._running and self._allowed():
            self._run(self.stepper.restart)

    def close(self) -> None:
        '''Closes the window, once the step running (if any) has stopped.'''
        self._closing = True
        self.stop()
        if not self._stepping:
            self.destroy()

    def _can_step(self) -> bool:
        return not self._stepping and self.stepper.snapshot is not None and \
            not self.stepper.done and self._allowed()

    def _run(self, action) -> Optional[Snapshot]:
        '''Runs a step (or restart) and shows it; None if it stopped or failed.'''
        self._stepping = True
        self.progress.stopped = False
        self.progress.training_text = ''
        self._update_buttons()
        snapshot = None
        try:
            snapshot = action()
        except RunStopped:
            self.show('Stopped')
        except Exception as error:
            print(traceback.format_exc(), file=sys.stderr)
            message = strip_ansi(str(error))
            self.show(f'Stopped by an error: {type(error).__name__}')
            if not self._closing:
                messagebox.showerror('pyRDDLGym error', message, parent=self)
                self._on_error(message)
        finally:
            self._stepping = False
        if self._closing:
            self.destroy()
            return None
        if snapshot is not None:
            self._show_snapshot(snapshot)
            if not self._running:
                self.show(HINT)
        self._update_buttons()
        return snapshot

    def _update_buttons(self) -> None:
        busy = self._stepping or self._running
        try:
            ready = self.stepper.snapshot is not None and not self.stepper.done
            self.buttons['step'].set_enabled(not busy and ready)
            self.buttons['run'].set_enabled(not busy and ready)
            self.buttons['stop'].set_enabled(busy)
            self.buttons['restart'].set_enabled(not busy)
        except TclError:
            pass
        self._busy_changed(busy)

    def _closed(self) -> None:
        AppearanceModeTracker.remove(self._recolor)
        self._running = False
        self._busy_changed(False)
        self._on_close(self.stepper.close())

    # ===========================================================================
    # what the step shows
    # ===========================================================================

    def show(self, text: str) -> None:
        '''Shows the text in the footer (also how the progress of planning is shown).'''
        self.footer.show(text)

    def _show_snapshot(self, snapshot: Snapshot) -> None:
        if snapshot.reward is None:
            text = f'Step 0/{snapshot.horizon} · initial state'
        else:
            text = f'Step {snapshot.step}/{snapshot.horizon} · ' \
                   f'reward {number(snapshot.reward)} · return {number(snapshot.total)}'
        if snapshot.done:
            text += ' · episode ended'
        self.status.configure(text=text)
        rows = []
        for (section, fluents) in snapshot.sections:
            rows.append((section, '', section, '', ('section',)))
            for (var, pairs) in fluents.items():
                iid = f'{section}/{var}'
                if len(pairs) == 1 and pairs[0][0] == var:
                    tags = ('changed',) if (section, var) in snapshot.highlighted else ()
                    rows.append((iid, section, var, _format(pairs[0][1]), tags))
                    continue
                changed = sum((section, g) in snapshot.highlighted for (g, _) in pairs)
                how = 'set' if section == 'Action' else 'changed'
                rows.append((iid, section, var,
                             f'{changed} of {len(pairs)} {how}' if changed else '', ()))
                for (grounding, value) in pairs:
                    tags = ('changed',) if (section, grounding) in snapshot.highlighted \
                        else ()
                    rows.append((f'{iid}/{grounding}', iid, grounding, _format(value), tags))
        self._rows = rows
        self._show_rows()
        self._show_picture()

    def _show_rows(self) -> None:
        '''Shows the rows that match the filter (with those they are in), updating the
        values in place when the same rows are shown as before.'''
        query = self.filter.get().strip().lower()
        rows = self._rows
        if query:
            parents = {iid: parent for (iid, parent, *_) in rows}
            keep = set()
            for (iid, parent, text, *_) in rows:
                if parent and query in text.lower():
                    keep.add(iid)
                    while parents.get(iid):
                        iid = parents[iid]
                        keep.add(iid)
            fluents = {iid for (iid, _, text, *_) in rows
                       if iid.count('/') == 1 and query in text.lower()}
            keep.update(iid for (iid, parent, *_) in rows if parent in fluents)
            rows = [row for row in rows if row[0] in keep]
        tree = self.tree
        iids = [row[0] for row in rows]
        if iids == getattr(self, '_shown', None):
            for (iid, _, _, value, tags) in rows:
                tree.item(iid, values=(value,), tags=tags)
            return
        tree.delete(*tree.get_children())
        for (iid, parent, text, value, tags) in rows:
            tree.insert(parent, 'end', iid=iid, text=text, values=(value,), tags=tags,
                        open=bool(query) or iid not in self._closed_iids)
        self._shown = iids

    def _opened(self, opened: bool) -> None:
        iid = self.tree.focus()
        if iid:
            (self._closed_iids.discard if opened else self._closed_iids.add)(iid)

    def _schedule_picture(self) -> None:
        if self._picture_pending is None:
            self._picture_pending = self.after(50, self._show_picture)

    def _show_picture(self) -> None:
        '''Shows the picture of the step as large as fits, keeping its proportions.'''
        self._picture_pending = None
        snapshot = self.stepper.snapshot
        if self.picture is None or snapshot is None or snapshot.image is None:
            return
        scale = ScalingTracker.get_widget_scaling(self)
        (width, height) = (self.picture.winfo_width(), self.picture.winfo_height())
        if width < 20 or height < 20:
            return
        image = snapshot.image
        fit = min(width / image.width, height / image.height)
        size = (max(1, round(image.width * fit / scale)),
                max(1, round(image.height * fit / scale)))
        self._picture = CTkImage(light_image=image, dark_image=image, size=size)
        self.picture.configure(image=self._picture)

    # ===========================================================================
    # appearance
    # ===========================================================================

    def _style(self) -> None:
        palette = ThemeManager.theme['Palette']
        color = self._apply_appearance_mode
        scale = ScalingTracker.get_widget_scaling(self)
        style = ttk.Style(self)
        if style.theme_use() != 'clam':
            style.theme_use('clam')
        family = CTkFont().cget('family')
        size = -round(FONT_SIZE * scale)
        (background, text, muted, accent, chrome, border) = (
            color(palette[key]) for key in
            ('content', 'text', 'text_muted', 'accent', 'chrome', 'border'))
        style.configure(STYLE, background=background, fieldbackground=background,
                        foreground=text, font=(family, size), borderwidth=0,
                        rowheight=round(ROW_HEIGHT * scale), indent=round(16 * scale))
        style.layout(STYLE, [('Treeview.treearea', {'sticky': 'nswe'})])
        style.map(STYLE, background=[('selected', _mix(accent, background, 0.3))],
                  foreground=[('selected', text)])
        style.configure(f'{STYLE}.Heading', background=chrome, foreground=muted,
                        font=(family, size), relief='flat', borderwidth=0,
                        lightcolor=chrome, darkcolor=chrome, bordercolor=border)
        style.map(f'{STYLE}.Heading', background=[('active', chrome)])
        style.configure(
            f'{STYLE}.Item', indicatorsize=round(9 * scale), indicatorforeground=muted)
        tree = self.tree
        tree.tag_configure('section', font=(family, size, 'bold'))
        tree.tag_configure('changed', background=_mix(accent, background, HIGHLIGHT_TINT))
        tree.column('#0', minwidth=round(160 * scale), stretch=True)
        tree.column('value', width=round(VALUE_WIDTH * scale),
                    minwidth=round(80 * scale), stretch=True, anchor='w')
        divider = color(ThemeManager.theme['CTk']['fg_color'])
        self.panes.configure(bg=divider)

    def _recolor(self, *_) -> None:
        self.after_idle(lambda: self.winfo_exists() and self._style())

    def _place(self) -> None:
        '''Sizes the window, up to SIZE, over the middle of its master.'''
        master = self.master
        window_scale = self._get_window_scaling()
        (w, h) = (min(SIZE[0] * window_scale, master.winfo_width() * 0.9),
                  min(SIZE[1] * window_scale, master.winfo_height() * 0.9))
        x = master.winfo_rootx() + (master.winfo_width() - w) / 2
        y = master.winfo_rooty() + (master.winfo_height() - h) / 3
        self.geometry(f'{round(w / window_scale)}x{round(h / window_scale)}'
                      f'+{max(0, round(x))}+{max(0, round(y))}')
        if self.picture is not None:
            self.after(50, lambda: self.panes.sash_place(0, round(w * 0.45), 0))
