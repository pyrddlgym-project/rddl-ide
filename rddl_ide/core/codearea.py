import tkinter
from tkinter import TclError, font
from customtkinter import AppearanceModeTracker, CTkTextbox, CTkScrollbar
from pygments import token
from pygments.styles import get_style_by_name
import re

PYTHON_GRAMMAR = [
    (token.Keyword, (r"\b(?P<KEYWORD>False|None|True|and|as|assert|async|await|"
                     r"break|class|continue|def|del|elif|else|except|finally|for|"
                     r"from|global|if|import|in|is|lambda|nonlocal|not|or|pass|"
                     r"raise|return|try|while|with|yield)\b")),
    (token.Keyword, r"\b(?P<INSTANCE>super|self|cls)\b"),
    (token.Keyword.Type, r"\b(?P<TYPES>bool|bytearray|bytes|dict|float|int|list|str|tuple|object)\b"),
    (token.Name.Builtin, (r"([^.'\"\\#]\b|^)(?P<BUILTIN>abs|all|any|ascii|bin|"
                          r"breakpoint|callable|chr|classmethod|compile|complex|"
                          r"copyright|credits|delattr|dir|divmod|enumerate|eval|"
                          r"exec|exit|filter|format|frozenset|getattr|globals|"
                          r"hasattr|hash|help|hex|id|input|isinstance|issubclass|"
                          r"iter|len|license|locals|map|max|memoryview|min|next|"
                          r"oct|open|ord|pow|print|quit|range|repr|reversed|"
                          r"round|set|setattr|slice|sorted|staticmethod|sum|"
                          r"type|vars|zip)\b")),
    (token.Name.Decorator, r"(^[ \t]*(?P<DECORATOR>@[\w\d\.]+))"),
    (token.String, (r"(?P<STRING>(?i:r|u|f|fr|rf|b|br|rb)?'[^'\\\n]*"
                    r"(\\.[^'\\\n]*)*'?|(?i:r|u|f|fr|rf|b|br|rb)?\"[^\"\\\n]*"
                    r"(\\.[^\"\\\n]*)*\"?)")),
    (token.String.Doc, (r"(?P<DOCSTRING>(?i:r|u|f|fr|rf|b|br|rb)?'''[^'\\]*((\\.|'"
                        r"(?!''))[^'\\]*)*(''')?|(?i:r|u|f|fr|rf|b|br|rb)?\"\"\""
                        r"[^\"\\]*((\\.|\"(?!\"\"))[^\"\\]*)*(\"\"\")?)")),
    (token.Number, r"\b(?P<NUMBER>((0x|0b|0o|#)[\da-fA-F]+)|((\d*\.)?\d+))\b"),
    (token.Comment, r"(?P<COMMENT>#[^\n]*)")
]

RDDL_GRAMMAR = [
    (token.Keyword, r'\b(?P<KEYWORD>if|then|else|switch|case|default|otherwise)\b'),
    (token.Keyword, (r'\b(?P<COMPONENT>domain|requirements|types|objects|pvariables|cpfs|cdfs|reward|'
                     r'action-preconditions|state-action-constraints|state-invariants|'
                     r'termination|terminate-when|terminal|policy|'
                     r'instance|init-state|non-fluents|max-nondef-actions|horizon|discount)\b')),
    (token.Keyword, (r'\b(?P<FTYPES>state-fluent|action-fluent|observ-fluent|'
                     r'interm-fluent|derived-fluent|non-fluent|param-fluent)\b')),
    (token.Keyword.Type, r'\b(?P<TYPES>bool|int|real|object)\b'),
    (token.Keyword.Constant, r'\b(?P<CONSTANT>true|false|pos-inf|neg-inf)\b'),
    (token.Name.Builtin, (r"([^.'\"\\#]\b|^)(?P<BUILTIN>abs|sgn|round|floor|ceil|cos|sin|tan|" 
                          r"acos|asin|atan|cosh|sinh|tanh|exp|ln|sqrt|lngamma|gamma|"
                          r"div|mod|fmod|min|max|pow|log|hypot|probe"
                          r")\b")),
    (token.Name.Builtin, r'\b(?P<AGGREGATION>sum|avg|prod|minimum|maximum|exists|forall|argmax|argmin)'),
    (token.Name.Builtin, r'\b(?P<MATRIX>det|inverse|pinverse|cholesky|row|col)\b'),
    (token.Name.Builtin, (r'\b(?P<RANDOM>KronDelta|DiracDelta|Bernoulli|Normal|Uniform|'
                          r'Poisson|Exponential|Weibull|Gamma|Binomial|NegativeBinomial|'
                          r'Beta|Geometric|Pareto|Student|Gumbel|Laplace|Cauchy|Gompertz|'
                          r'ChiSquare|Kumaraswamy|Discrete|UnnormDiscrete|'
                          r'Discrete(p)|UnnormDiscrete(p)'
                          r')')),
    (token.Name.Builtin, (r'\b(?P<RANDOMVECTOR>MultivariateNormal|MultivariateStudent|'
                          r'Dirichlet|Multinomial)')),
    (token.Name.Variable, r"\?([^,:;+\-\*\/\s}\)\]]+)"),
    (token.Literal, r"\@([^,:;+\-\*\/\s}\)\]]+)"),
    (token.Number, r"\b(?P<NUMBER>((0x|0b|0o|#)[\da-fA-F]+)|((\d*\.)?\d+))\b"),
    (token.Comment, r'(?P<COMMENT>//[^\n]*)')
]
        

# a muted red behind the text, which stays legible in both themes, underlined in red
ERROR_BACKGROUND = ('#ffdcdc', '#5a1d22')
ERROR_UNDERLINE = ('#d00000', '#ff6b6b')
ERROR_TAG = 'rddl_error'
FONT_SIZE = 14


# pygments styles that color the code in the light and the dark theme
SYNTAX_STYLES = ('default', 'monokai')


class CTkCodeViewer(CTkTextbox):

    def __init__(self, *args, width: int=100, height: int=32,
                 language='python', theme=SYNTAX_STYLES, **kwargs):
        kwargs.setdefault('undo', True)
        kwargs.setdefault('maxundo', -1)
        super().__init__(*args, width=width, height=height, **kwargs)
        self.styles = theme
        if language == 'python':
            self.patterns = PYTHON_GRAMMAR
        else:
            self.patterns = RDDL_GRAMMAR
        self.bind("<KeyRelease>", lambda *_: self.apply())
        self.bind('<KeyPress>', self._word_boundary)
        self._style_tags()

    def _word_boundary(self, event):
        '''Ends an undo step before each space, tab or new line typed, so that undo takes
        back about a word at a time rather than everything typed in one go.'''
        if event.char in (' ', '\t', '\r', '\n'):
            self.edit_separator()

    def set_text(self, text):
        '''Replaces the whole text, as when a file is opened, which cannot be undone.'''
        self.delete('1.0', 'end')
        self.insert('1.0', text)
        self.edit_reset()
        self.apply()

    def _style_tags(self):
        '''Colors the syntax and error tags for the current theme.'''
        style = get_style_by_name(self._apply_appearance_mode(self.styles))
        for (tag, _) in self.patterns:
            color = style.style_for_token(tag)['color']
            self.tag_config(str(tag), foreground='#' + color if color else '')
        self.tag_config(ERROR_TAG, background=self._apply_appearance_mode(ERROR_BACKGROUND),
                        underline=True,
                        underlinefg=self._apply_appearance_mode(ERROR_UNDERLINE))
        self.tag_lower(ERROR_TAG, 'sel')  # a selection inside the error stays visible

    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        self._style_tags()

    def show_error(self, start, end):
        '''Marks the source an error points to and scrolls it into view.'''
        self.clear_error()
        self.tag_add(ERROR_TAG, start, end)
        self.see(end)
        self.see(start)

    def clear_error(self):
        self.tag_remove(ERROR_TAG, '1.0', 'end')

    def apply(self):
        '''Highlights the syntax, removing the highlighting of text that no longer matches.'''
        lines = self.get('1.0', 'end').splitlines()
        for tag in {str(tag) for (tag, _) in self.patterns}:  # patterns can share a tag
            self.tag_remove(tag, '1.0', 'end')
        for (tag, pattern) in self.patterns:
            for (i, line) in enumerate(lines, 1):
                for found in re.finditer(pattern, line):
                    self.tag_add(str(tag), f'{i}.{found.start()}', f'{i}.{found.end()}')


class LineNumbers(tkinter.Canvas):
    '''A gutter showing the number of each visible line of a code viewer at the height
    of that line, redrawn whenever the view scrolls, the text changes or it resizes.'''

    PADDING = 8

    def __init__(self, master, viewer: CTkTextbox):
        super().__init__(master, highlightthickness=0, bd=0, width=1)
        self.viewer = viewer
        self.textbox = viewer._textbox
        self._pending = False

        # the text calls its yscrollcommand whenever its view changes, however scrolled
        scrollbar_set = viewer._y_scrollbar.set

        def scrolled(*args):
            scrollbar_set(*args)
            self.schedule()

        self.textbox.configure(yscrollcommand=scrolled)
        self.textbox.bind('<<Modified>>', self._modified, add='+')
        self.textbox.bind('<Configure>', self.schedule, add='+')
        self.bind('<Configure>', self.schedule, add='+')
        self.bind('<MouseWheel>', lambda event: self.textbox.event_generate(
            '<MouseWheel>', delta=event.delta))
        AppearanceModeTracker.add(self.schedule, self)
        self.bind('<Destroy>', lambda _: AppearanceModeTracker.remove(self.schedule), add='+')
        self.schedule()

    def _modified(self, _=None):
        self.textbox.edit_modified(False)  # so that the next change is reported too
        self.schedule()

    def schedule(self, *_):
        '''Redraws once the text has laid out its lines.'''
        if not self._pending:
            self._pending = True
            self.after_idle(self.redraw)

    def redraw(self):
        self._pending = False
        try:
            color = self.viewer._apply_appearance_mode
            text_font = font.Font(font=self.textbox.cget('font'))
            last = int(self.textbox.index('end-1c').split('.')[0])
            width = text_font.measure('0' * len(str(last))) + 2 * self.PADDING
            self.configure(width=width, bg=color(self.viewer.cget('fg_color')))
            self.delete('all')

            # dlineinfo is relative to the text, which is inset in the viewer
            top = self.textbox.winfo_rooty() - self.winfo_rooty()
            first = int(self.textbox.index('@0,0').split('.')[0])
            for line in range(first, last + 1):
                info = self.textbox.dlineinfo(f'{line}.0')
                if info is None:  # below the visible part
                    break
                self.create_text(width - self.PADDING, top + info[1], anchor='ne',
                                 text=str(line), font=text_font,
                                 fill=color(self.viewer.cget('text_color')))
        except TclError:  # the editor was closed
            pass


# monospace fonts in order of preference: Windows, macOS, then common Linux fonts
MONOSPACE_FAMILIES = ('Consolas', 'Menlo', 'SF Mono', 'DejaVu Sans Mono', 'Liberation Mono',
                      'Ubuntu Mono', 'Noto Sans Mono', 'Courier New')


def monospace_family() -> str:
    '''The first installed font of MONOSPACE_FAMILIES, else Courier, which Tk maps to a
    monospace font on every platform.'''
    installed = set(font.families())
    return next((family for family in MONOSPACE_FAMILIES if family in installed), 'Courier')


class CodeEditor:
    
    def __init__(self, window, language, theme=SYNTAX_STYLES):
        my_font = monospace_family()
        text_area = CTkCodeViewer(
            window, font=(my_font, FONT_SIZE), language=language, theme=theme, wrap='none')
        self.text = text_area
        
        LineNumbers(window, text_area).pack(side='left', fill='y')
        text_area.pack(expand=True, fill='both')        
        CTkScrollbar(window, command=text_area.xview)
        CTkScrollbar(window, command=text_area.yview)
        
