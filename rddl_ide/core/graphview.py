'''A window showing the dependency graph of the domain: the fluents each CPF and the
reward depend on, in columns by the order pyRDDLGym evaluates them.'''
import tkinter
from tkinter import font
from typing import Callable, Dict, List, Optional, Tuple

from customtkinter import (
    AppearanceModeTracker, CTkCheckBox, CTkFont, CTkFrame, CTkLabel, CTkScrollbar,
    CTkToplevel, ScalingTracker, ThemeManager
)

from rddl_ide.core.appicon import set_icon
from rddl_ide.core.dependencies import Graph, Node, REWARD, dependency_graph
from rddl_ide.core.errorlocation import strip_ansi
from rddl_ide.core.icons import IconButton
from rddl_ide.core.statusbar import StatusLine
from rddl_ide.core.titlebar import match_title_bar

# sizes, before scaling
FONT_SIZE = 13
NODE_HEIGHT = 26
NODE_PADDING = 12
ROW_GAP = 10
COLUMN_GAP = 72
MARGIN = 24
HEADER_HEIGHT = 28
LANE = 8
SWEEPS = 4
WAYPOINT = 'waypoint'
MAX_SIZE = (1280, 760)

# (light, dark) colors of the kinds of nodes, with their names in the legend
KINDS = {
    'non-fluent': ('Non-fluent', ('#6B717A', '#8C9099')),
    'state-fluent': ('State', ('#2F6FEB', '#5B8EF5')),
    'action-fluent': ('Action', ('#C2410C', '#F0883E')),
    'interm-fluent': ('Intermediate', ('#8250DF', '#A984F0')),
    'derived-fluent': ('Derived', ('#8250DF', '#A984F0')),
    'next-state-fluent': ('Next state', ('#1A7F37', '#3FB950')),
    'observ-fluent': ('Observation', ('#0E7490', '#39C5CF')),
    REWARD: ('Reward', ('#CF222E', '#F85149')),
}
FILL_TINT = 0.14
HINT = 'Point at a fluent to see what it depends on and what uses it; ' \
       'click it to go to its definition.'

Source = Callable[[], Tuple[str, str]]


def _mix(color: str, background: str, amount: float) -> str:
    '''The color amount of the way from the background to the color.'''
    (a, b) = (int(color[1:], 16), int(background[1:], 16))
    channels = [round(((b >> s) & 255) * (1 - amount) + ((a >> s) & 255) * amount)
                for s in (16, 8, 0)]
    return '#' + ''.join(f'{c:02x}' for c in channels)


def _rounded_rectangle(x1, y1, x2, y2, r) -> List[float]:
    '''The points of a rectangle with rounded corners, as a smoothed polygon.'''
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def arrange(graph: Graph) -> Tuple[List[List[Node]], Dict[Tuple[str, str], List[str]]]:
    '''The nodes in their columns, ordered to reduce crossing edges by sweeping back and
    forth, each node moved to the mean position of its neighbors in the column before
    (or after); the inputs stay grouped by kind. An edge across columns passes each
    column between by a waypoint, a node of kind WAYPOINT ordered with the others,
    which are returned by edge.'''
    columns: List[List[Node]] = [[] for _ in range(1 + max(n.column for n in graph.nodes))]
    for node in graph.nodes:
        columns[node.column].append(node)
    column_of = {node.name: node.column for node in graph.nodes}
    (sources, targets) = ({}, {})
    waypoints: Dict[Tuple[str, str], List[str]] = {}
    for (dep, name) in graph.edges:
        chain = [dep]
        for c in range(column_of[dep] + 1, column_of[name]):
            columns[c].append(Node(f'{dep}\0{name}\0{c}', WAYPOINT, c, ''))
            chain.append(columns[c][-1].name)
        chain.append(name)
        waypoints[(dep, name)] = chain[1:-1]
        for (u, v) in zip(chain, chain[1:]):
            sources.setdefault(v, []).append(u)
            targets.setdefault(u, []).append(v)

    def place():
        return {node.name: (i + 0.5) / len(column)
                for column in columns for (i, node) in enumerate(column)}

    def order(column, neighbors, position, grouped=False):
        def key(item):
            (i, node) = item
            linked = [position[n] for n in neighbors.get(node.name, ()) if n in position]
            mean = sum(linked) / len(linked) if linked else (i + 0.5) / len(column)
            return (_group(node) if grouped else 0, mean)
        return [node for (_, node) in sorted(enumerate(column), key=key)]

    for _ in range(SWEEPS):
        for c in range(1, len(columns)):
            columns[c] = order(columns[c], sources, place())
        for c in range(len(columns) - 2, -1, -1):
            columns[c] = order(columns[c], targets, place(), grouped=c == 0)
    return (columns, waypoints)


def _group(node: Node) -> int:
    return list(KINDS).index(node.kind) if node.kind in KINDS else len(KINDS)


class DependencyWindow(CTkToplevel):
    '''The graph of the domain and instance given by source(), made again when they have
    changed as the window gets the focus; go_to(name) shows where a fluent is defined.'''

    def __init__(self, master, source: Source, go_to: Callable[[str], None]):
        palette = ThemeManager.theme['Palette']
        super().__init__(master)
        self.title('Dependency Graph')
        self.transient(master)
        self.after(250, lambda: set_icon(self))
        match_title_bar(self)
        self.source = source
        self.go_to = go_to
        self.graph: Optional[Graph] = None
        self.error: Optional[str] = None
        self._built_from = None
        self._hovered: Optional[str] = None
        self._sized = False

        bar = CTkFrame(self, corner_radius=0, fg_color=palette['chrome'])
        bar.pack(side='top', fill='x')
        CTkFrame(bar, height=1, corner_radius=0, fg_color=palette['border']).pack(
            side='bottom', fill='x')
        text_font = CTkFont(size=FONT_SIZE)
        self.non_fluents = tkinter.BooleanVar(self, False)
        CTkCheckBox(bar, text='Non-fluents', variable=self.non_fluents, font=text_font,
                    checkbox_width=18, checkbox_height=18, border_width=1,
                    command=self.refresh).pack(side='left', padx=(10, 16), pady=6)
        self.legend = CTkFrame(bar, fg_color='transparent')
        self.legend.pack(side='left')
        IconButton(bar, 'refresh', 'Rebuild from the domain and instance',
                   self.refresh).pack(side='right', padx=4)

        self.footer = StatusLine(self, HINT)
        self.footer.pack(side='bottom', fill='x')
        area = CTkFrame(self, corner_radius=0, fg_color='transparent')
        area.pack(side='top', fill='both', expand=True)
        self.canvas = tkinter.Canvas(area, highlightthickness=0, borderwidth=0)
        y_bar = CTkScrollbar(area, orientation='vertical', command=self.canvas.yview)
        x_bar = CTkScrollbar(area, orientation='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=y_bar.set, xscrollcommand=x_bar.set)
        y_bar.pack(side='right', fill='y')
        x_bar.pack(side='bottom', fill='x')
        self.canvas.pack(side='left', fill='both', expand=True)
        for (prefix, horizontal) in (('', False), ('Shift-', True)):
            for event in ('MouseWheel', 'Button-4', 'Button-5'):  # X11 sends buttons
                self.canvas.bind(f'<{prefix}{event}>', lambda e, h=horizontal:
                                 self._scroll(e, horizontal=h))
        self.canvas.bind('<Configure>', lambda _: self._place_message())

        self.bind('<Escape>', lambda _: self.destroy())
        self.bind('<FocusIn>', lambda e: e.widget is self and self.refresh(changed=True),
                  add='+')
        AppearanceModeTracker.add(self._recolor, self)
        self.bind('<Destroy>', 
                  lambda e: e.widget is self and
                    AppearanceModeTracker.remove(self._recolor), add='+')
        self.refresh()

    # ===========================================================================
    # building
    # ===========================================================================

    def refresh(self, changed: bool=False) -> None:
        '''Builds the graph again, or only if the domain, instance or the choice of
        non-fluents changed since it was built.'''
        try:
            texts = self.source()
        except tkinter.TclError:
            return
        built_from = (texts, self.non_fluents.get())
        if changed and built_from == self._built_from:
            return
        self._built_from = built_from
        try:
            self.graph = dependency_graph(*texts, include_non_fluents=built_from[1])
            self.error = None
        except Exception as error:
            self.graph = None
            self.error = strip_ansi(str(error)).strip() or type(error).__name__
        self._hovered = None
        self.draw()

    # ===========================================================================
    # drawing
    # ===========================================================================

    def _color(self, colors) -> str:
        return self._apply_appearance_mode(colors)

    def draw(self) -> None:
        palette = ThemeManager.theme['Palette']
        canvas = self.canvas
        canvas.delete('all')
        canvas.configure(bg=self._color(palette['content']))
        self.footer.show(HINT)
        self._draw_legend()
        scale = ScalingTracker.get_widget_scaling(self)
        self._font = font.Font(
            family=CTkFont().cget('family'), size=-round(FONT_SIZE * scale))
        self.nodes: Dict[str, Tuple[int, int]] = {}
        self.edges: List[Tuple[str, str, int]] = []
        if self.graph is None:
            self._message = canvas.create_text(
                0, 0, text=f'Could not build the graph:\n\n{self.error}', anchor='nw',
                fill=self._color(palette['text_muted']), font=self._font, justify='left')
            self._place_message()
            canvas.configure(scrollregion=(0, 0, 0, 0))
            return
        self._message = None
        (columns, waypoints) = arrange(self.graph)
        (height, gap, pad) = (NODE_HEIGHT * scale, ROW_GAP * scale, NODE_PADDING * scale)
        (margin, top, lane) = (MARGIN * scale, (MARGIN + HEADER_HEIGHT) * scale, LANE * scale)

        def slot(node):
            return lane if node.kind == WAYPOINT else height + gap

        widths = [max((self._font.measure(n.name) + 2 * pad for n in column
                       if n.kind != WAYPOINT), default=0) for column in columns]
        total = max(sum(slot(n) for n in column) for column in columns)
        boxes: Dict[str, Tuple[float, float, float, float]] = {}
        x = margin
        last = len(columns) - 1
        for (c, column) in enumerate(columns):
            title = 'Inputs' if c == 0 else 'Reward' if c == last else f'Level {c - 1}'
            canvas.create_text(x + widths[c] / 2, margin, text=title, anchor='n',
                               fill=self._color(palette['text_muted']), font=self._font)
            y = top + (total - sum(slot(n) for n in column)) / 2
            for node in column:
                if node.kind == WAYPOINT:
                    boxes[node.name] = (x, y, x + widths[c], y + lane)
                else:
                    boxes[node.name] = (x, y + gap / 2, x + widths[c], y + gap / 2 + height)
                y += slot(node)
            x += widths[c] + COLUMN_GAP * scale
        bend = COLUMN_GAP * scale / 2
        for (dep, name) in self.graph.edges:
            (x0, y0) = (boxes[dep][2], (boxes[dep][1] + boxes[dep][3]) / 2)
            (x3, y3) = (boxes[name][0], (boxes[name][1] + boxes[name][3]) / 2)
            points = [x0, y0, x0 + bend, y0]
            for waypoint in waypoints[(dep, name)]:
                (left, y1, right, y2) = boxes[waypoint]
                points += [left - bend / 2, (y1 + y2) / 2, right + bend / 2, (y1 + y2) / 2]
            points += [x3 - bend, y3, x3, y3]
            item = canvas.create_line(
                *points, smooth=True, splinesteps=24, arrow='last',
                arrowshape=(7 * scale, 8 * scale, 3 * scale), tags=('edge',))
            self.edges.append((dep, name, item))
        for node in self.graph.nodes:
            (x1, y1, x2, y2) = boxes[node.name]
            tag = f'node{len(self.nodes)}'
            shape = canvas.create_polygon(
                _rounded_rectangle(x1, y1, x2, y2, 6 * scale), smooth=True,
                width=max(1, round(scale)), tags=('node', tag))
            text = canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=node.name,
                                      font=self._font, tags=('node', tag))
            self.nodes[node.name] = (shape, text)
            canvas.tag_bind(tag, '<Enter>', lambda _, n=node: self._hover(n))
            canvas.tag_bind(tag, '<Leave>', lambda _: self._hover(None))
            canvas.tag_bind(tag, '<Button-1>', lambda _, n=node: self.go_to(n.name))
        self._paint()
        (_, _, right, bottom) = canvas.bbox('all')
        canvas.configure(scrollregion=(0, 0, right + margin, bottom + margin))
        if not self._sized:
            self._sized = True
            self._fit(right + margin, bottom + margin, scale)

    def _paint(self) -> None:
        '''Colors the nodes and edges, those of the node pointed at highlighted.'''
        palette = ThemeManager.theme['Palette']
        (background, text, muted, accent) = (
            self._color(palette[key]) for key in ('content', 'text', 'text_muted', 'accent'))
        edge = self._color(palette['scrollbar'])
        hovered = self._hovered
        related = {hovered} if hovered else set()
        for (dep, name, _) in self.edges:
            if hovered in (dep, name):
                related.update((dep, name))
        canvas = self.canvas
        scale = ScalingTracker.get_widget_scaling(self)
        for node in self.graph.nodes:
            (shape, label) = self.nodes[node.name]
            color = self._color(KINDS.get(node.kind, KINDS['interm-fluent'])[1])
            if hovered and node.name not in related:
                canvas.itemconfigure(shape, fill=background,
                                     outline=self._color(palette['border']))
                canvas.itemconfigure(label, fill=muted)
            else:
                canvas.itemconfigure(shape, fill=_mix(color, background, FILL_TINT * (
                    2 if node.name == hovered else 1)), outline=color)
                canvas.itemconfigure(label, fill=text)
        for (dep, name, item) in self.edges:
            if hovered in (dep, name):
                canvas.itemconfigure(item, fill=accent, width=2 * scale)
                canvas.tag_raise(item)
            else:
                canvas.itemconfigure(item, fill=_mix(edge, background, 0.35)
                                     if hovered else edge, width=max(1, round(scale)))
        canvas.tag_raise('node')

    def _hover(self, node: Optional[Node]) -> None:
        self._hovered = node.name if node is not None else None
        self.canvas.configure(cursor='hand2' if node is not None else '')
        if node is None:
            self.footer.show(HINT)
        else:
            uses = [dep for (dep, name) in self.graph.edges if name == node.name]
            used_by = [name for (dep, name) in self.graph.edges if dep == node.name]
            kind = KINDS.get(node.kind, (node.kind,))[0]
            self.footer.show(f'{kind}  {node.signature}   ·   depends on: '
                             f'{", ".join(uses) or "nothing"}   ·   used by: '
                             f'{", ".join(used_by) or "nothing"}')
        self._paint()

    def _draw_legend(self) -> None:
        for child in self.legend.winfo_children():
            child.destroy()
        if self.graph is None:
            return
        palette = ThemeManager.theme['Palette']
        shown = {node.kind for node in self.graph.nodes}
        for (kind, (name, colors)) in KINDS.items():
            if kind in shown:
                CTkLabel(self.legend, text='■', text_color=colors, width=0, padx=0,
                         font=CTkFont(size=FONT_SIZE)).pack(side='left', padx=(0, 4))
                CTkLabel(self.legend, text=name, text_color=palette['text'], width=0,
                         padx=0, font=CTkFont(size=FONT_SIZE)).pack(
                    side='left', padx=(0, 14))

    def _place_message(self) -> None:
        if getattr(self, '_message', None) is not None:
            margin = MARGIN * ScalingTracker.get_widget_scaling(self)
            width = self.canvas.winfo_width()
            self.canvas.coords(self._message, margin, margin)
            self.canvas.itemconfigure(self._message, width=max(200, width - 2 * margin))

    def _fit(self, width, height, scale) -> None:
        '''Sizes the window to the graph, up to MAX_SIZE, over the middle of its master.'''
        self.update_idletasks()
        extra = (self.winfo_reqwidth() - self.canvas.winfo_reqwidth(),
                 self.winfo_reqheight() - self.canvas.winfo_reqheight())
        (w, h) = (min(width + extra[0], MAX_SIZE[0] * scale),
                  min(height + extra[1], MAX_SIZE[1] * scale))
        (w, h) = (max(w, 560 * scale), max(h, 320 * scale))
        master = self.master
        x = master.winfo_rootx() + (master.winfo_width() - w) / 2
        y = master.winfo_rooty() + (master.winfo_height() - h) / 3
        window_scale = self._get_window_scaling()
        self.geometry(f'{round(w / window_scale)}x{round(h / window_scale)}'
                      f'+{max(0, round(x))}+{max(0, round(y))}')

    def _recolor(self, *_) -> None:
        self.after_idle(lambda: self.winfo_exists() and self.draw())

    def _scroll(self, event, horizontal: bool=False) -> None:
        '''Scrolls by the wheel: its delta is a multiple of 120 on Windows, small on
        macOS, and X11 reports it as button 4 (up) or 5 (down).'''
        if event.num in (4, 5):
            steps = -1 if event.num == 4 else 1
        elif event.delta:
            steps = -round(event.delta / 120) or (-1 if event.delta > 0 else 1)
        else:
            return
        (self.canvas.xview_scroll if horizontal else self.canvas.yview_scroll)(
            steps, 'units')
