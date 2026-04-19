import customtkinter
from CTkMenuBar import CTkMenuBar

from rddl_ide.core.codearea import CodeEditor
from rddl_ide.core.menubar import assign_menubar_functions


def main():

    # domain window
    domain_window = customtkinter.CTk()
    domain_window.title('[Domain] Untitled')
    w, h = domain_window._max_width, domain_window._max_height
    w = domain_window.winfo_screenwidth()
    h = domain_window.winfo_screenheight()
    w = int(w * 0.99)
    h = int(h * 0.9)
    wd = int(0.6 * w)
    domain_window.geometry(f'{wd}x{h}+0+0')
    domain_window.resizable(height=None, width=None)
    domain_window.columnconfigure(0, weight=1)
    domain_window.rowconfigure(0, weight=1)
    
    # instance window
    inst_window = customtkinter.CTkToplevel(domain_window)
    inst_window.title('[Instance] Untitled')
    wi = w - wd
    inst_window.geometry(f'{wi}x{h // 2}+{wd}+0')
    inst_window.resizable(height=None, width=None)
    inst_window.columnconfigure(0, weight=1)
    inst_window.rowconfigure(0, weight=1)
    
    # policy window
    policy_window = customtkinter.CTkToplevel(domain_window)
    policy_window.title('[Policy] Policy')
    o = 35
    policy_window.geometry(f'{wi}x{h // 2 - o}+{wd}+{h // 2 + o}')
    policy_window.resizable(height=None, width=None)
    policy_window.columnconfigure(0, weight=1)
    policy_window.rowconfigure(0, weight=1)
    
    # text editors
    domain_menu = CTkMenuBar(domain_window)
    inst_menu = CTkMenuBar(inst_window)
    policy_menu = CTkMenuBar(policy_window)
    domain_editor = CodeEditor(domain_window, 'rddl')
    inst_editor = CodeEditor(inst_window, 'rddl')
    policy_editor = CodeEditor(policy_window, 'python')
    
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
