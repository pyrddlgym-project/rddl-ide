from customtkinter import CTk, CTkToplevel, set_appearance_mode, set_default_color_theme
from CTkMenuBar import CTkMenuBar

from rddl_ide.core.codearea import CodeEditor
from rddl_ide.core.menubar import assign_menubar_functions


class ToplevelWindow(CTkToplevel):

    def __init__(self, *args, **kwargs):
        super(ToplevelWindow, self).__init__(*args, **kwargs)
        self.after(250, lambda: self.iconbitmap('icon.ico'))
        
        
def main():
    set_appearance_mode("system")
    set_default_color_theme("theme.json")
    
    # domain window
    domain_window = CTk()
    domain_window.title('[Domain] Untitled')
    domain_window.wm_iconbitmap('icon.ico')
    w, h = domain_window._max_width, domain_window._max_height
    w = domain_window.winfo_screenwidth()
    h = domain_window.winfo_screenheight()
    w = int(w * 0.995)
    h = int(h * 0.995)
    wd = int(0.6 * w)
    domain_window.geometry(f'{wd}x{h}+0+0')
    domain_window.resizable(height=None, width=None)
    
    # instance window
    inst_window = ToplevelWindow(domain_window)
    inst_window.title('[Instance] Untitled')
    inst_window.geometry(f'{w - wd}x{h // 2}+{wd}+0')
    inst_window.resizable(height=None, width=None)
    
    # policy window
    policy_window = ToplevelWindow(domain_window)
    policy_window.title('[Policy] Policy')
    policy_window.geometry(f'{w - wd}x{h // 2 - 30}+{wd}+{h // 2 + 30}')
    policy_window.resizable(height=None, width=None)
    
    # text editors
    domain_menu = CTkMenuBar(domain_window)
    inst_menu = CTkMenuBar(inst_window)
    policy_menu = CTkMenuBar(policy_window)
    domain_editor = CodeEditor(domain_window, language='rddl')
    inst_editor = CodeEditor(inst_window, language='rddl')
    policy_editor = CodeEditor(policy_window, language='python')
    
    # menu bars
    assign_menubar_functions(domain_menu, domain_window,
                             inst_menu, inst_window,
                             policy_menu, policy_window,
                             domain_editor.text, inst_editor.text, policy_editor.text)
    domain_window.update()
    domain_window.mainloop()
    inst_window.update()
    inst_window.mainloop()
    policy_window.update()
    policy_window.mainloop()


if __name__ == '__main__':
    main()
