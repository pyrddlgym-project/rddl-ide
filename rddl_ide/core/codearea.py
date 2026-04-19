from tkinter import font
from customtkinter import CTkTextbox, CTkScrollbar
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
    (token.Keyword, r'\b(?P<KEYWORD>if|then|else|switch|case|default)\b'),
    (token.Keyword, (r'\b(?P<COMPONENT>domain|requirements|types|objects|pvariables|cpfs|reward|'
                     r'action-preconditions|state-invariants|termination|'
                     r'instance|init-state|non-fluents|max-nondef-actions|horizon|discount)\b')),
    (token.Keyword, (r'\b(?P<FTYPES>state-fluent|action-fluent|observ-fluent|'
                     r'interm-fluent|derived-fluent|non-fluent)\b')),
    (token.Keyword.Type, r'\b(?P<TYPES>bool|int|real|object)\b'),
    (token.Name.Builtin, (r"([^.'\"\\#]\b|^)(?P<BUILTIN>abs|sgn|round|floor|ceil|cos|sin|tan|" 
                          r"acos|asin|atan|cosh|sinh|tanh|exp|ln|sqrt|lngamma|gamma|"
                          r"div|mod|fmod|min|max|pow|log|hypot"
                          ")\b")),
    (token.Name.Builtin, r'\b(?P<AGGREGATION>sum|avg|prod|minimum|maximum|exists|forall|argmax|argmin)'),
    (token.Name.Builtin, r'\b(?P<MATRIX>det|inverse|pinverse|cholesky)'),
    (token.Name.Builtin, (r'\b(?P<RANDOM>KronDelta|DiracDelta|Bernoulli|Normal|Uniform|'
                          r'Poisson|Exponential|Weibull|Gamma|Binomial|NegativeBinomial|'
                          r'Beta|Geometric|Pareto|Student|Gumbel|Laplace|Cauchy|Gompertz|'
                          r'ChiSquared|Kumaraswamy|Discrete|UnnormDiscrete|'
                          r'Discrete(p)|UnnormDiscrete(p)'
                          r')')),
    (token.Name.Builtin, (r'\b(?P<RANDOMVECTOR>MultivariateNormal|MultivariateStudent|'
                          r'Dirichlet|Multinomial)')),
    (token.Name.Variable, r"\?([^,:;+\-\*\/\s}\)\]]+)"),
    (token.Literal, r"\@([^,:;+\-\*\/\s}\)\]]+)"),
    (token.Number, r"\b(?P<NUMBER>((0x|0b|0o|#)[\da-fA-F]+)|((\d*\.)?\d+))\b"),
    (token.Comment, r'(?P<COMMENT>//[^\n]*)')
]
        

class CTkCodeViewer(CTkTextbox):

    def __init__(self, *args, width: int=100, height: int=32, 
                 language='python', theme='monokai', **kwargs):
        super().__init__(*args, width=width, height=height, **kwargs)
        
        style_parsed = get_style_by_name(theme).list_styles()
        for key in style_parsed:
            if key[1]["color"] != "" and key[1]["color"] != None:
                self.tag_config(tagName=str(key[0]), foreground="#" + key[1]["color"])
        if language == 'python':
            self.patterns = PYTHON_GRAMMAR
        else:
            self.patterns = RDDL_GRAMMAR
        self.bind("<KeyRelease>", lambda *args: self.apply())
        
    def apply(self):
        for (tag, pattern) in self.patterns:
            text = self.get('0.0', 'end').splitlines()
            for (i, line) in enumerate(text):
                for found in re.finditer(pattern, line):
                    self.tag_add(
                        str(tag), f"{i + 1}.{found.start()}", f"{i + 1}.{found.end()}")


class TextLineNumbers(CTkTextbox):

    def __init__(self, master, text_widget, **kwargs):
        super().__init__(master, activate_scrollbars=False, **kwargs)
 
        self.text_widget = text_widget
        for tag in ['<KeyRelease>', '<FocusIn>', '<MouseWheel>', '<Configure>', '<<Modified>>']:
            self.text_widget.bind(tag, self.on_key_release)
        
    def on_key_release(self, event=None):
        p = int(self.text_widget.index("@0,0").split('.')[0])
        final_index = str(self.text_widget.index('end'))
        num_of_lines = int(final_index.split('.')[0])
        line_numbers_string = "\n".join(str(p + no) for no in range(num_of_lines))
                
        self.configure(state='normal')
        self.delete(0.0, 'end')
        self.insert(0.0, line_numbers_string)
        self.configure(state='disabled')
            

class CodeEditor:
    
    def __init__(self, window, language, theme='monokai'):
        if 'Consolas' in font.names() or 'Consolas' in font.families():
            my_font = 'Consolas'
        else:
            my_font = 'Courier'
        text_area = CTkCodeViewer(
            window, font=(my_font, 16), language=language, theme=theme, wrap='none')
        self.text = text_area
        
        ln = TextLineNumbers(window, text_area, width=50, font=(my_font, 16))
        ln.pack(side='left', fill='both')
        text_area.pack(expand=True, fill='both')        
        CTkScrollbar(window, command=text_area.xview)
        CTkScrollbar(window, command=text_area.yview)
        
