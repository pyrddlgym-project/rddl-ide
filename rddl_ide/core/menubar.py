import os
import sys
import traceback
from tkinter import messagebox
from customtkinter import CTkToplevel, StringVar, CTkLabel, CTkButton, CTkEntry
from customtkinter import get_appearance_mode, set_appearance_mode
from customtkinter import filedialog as fd

from rddl_ide.core.appicon import set_icon
from rddl_ide.core.errorlocation import locate_error
from rddl_ide.core.execution import evaluate_policy
from rddl_ide.core.popup import ChoiceMenu, MenuBarMenu
from rddl_ide.core.settings.registry import PROVIDERS


def assign_menubar_functions(menu, root, domain_pane, inst_pane, policy_pane,
                             domain_editor, inst_editor):
    policy_editor = policy_pane.text
    domain_file, inst_file, viz = None, None, None
    
    # load template RDDL
    abs_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(abs_path, 'prefab', 'domain.rddl'), 'r') as dom_txt:
        DOMAIN_TEMPLATE = dom_txt.read()
    with open(os.path.join(abs_path, 'prefab', 'instance.rddl'), 'r') as inst_txt:
        INSTANCE_TEMPLATE = inst_txt.read()
    
    # FILE functions
    def create_domain():
        nonlocal domain_file, viz
        domain_file, viz = None, None
        domain_pane.title('Domain: Untitled')
        domain_editor.delete(1.0, 'end')
        domain_editor.insert(1.0, DOMAIN_TEMPLATE)
        domain_editor.apply()
        
    def create_instance():
        nonlocal inst_file
        inst_file = None
        inst_pane.title('Instance: Untitled')
        inst_editor.delete(1.0, 'end')
        inst_editor.insert(1.0, INSTANCE_TEMPLATE)
        inst_editor.apply()
    
    def _pane_from_file(window, editor, caption, file_path):
        if file_path is not None:
            window.title(f'{caption}: {os.path.basename(file_path)}')
            editor.delete(1.0, 'end')
            with open(file_path, 'r') as new_file:
                editor.insert(1.0, new_file.read())
                new_file.close()
            editor.apply()
        
    def open_domain():
        nonlocal domain_file, viz    
        domain_file = fd.askopenfilename(defaultextension='.rddl',
                                         filetypes=[('RDDL File', '*.rddl*')])
        viz = None
        if domain_file == '': domain_file = None            
        _pane_from_file(domain_pane, domain_editor, 'Domain', domain_file)
    
    def open_instance():
        nonlocal inst_file        
        inst_file = fd.askopenfilename(defaultextension='.rddl',
                                       filetypes=[('RDDL File', '*.rddl*')])
        if inst_file == '': inst_file = None            
        _pane_from_file(inst_pane, inst_editor, 'Instance', inst_file)
    
    
    class ToplevelWindow(CTkToplevel):
    
        def __init__(self, *args, **kwargs):
            super(ToplevelWindow, self).__init__(*args, **kwargs)
            self.after(250, lambda: set_icon(self))  # after CTkToplevel sets its own
        
    def open_from_dialog():
        nonlocal domain_file, inst_file, viz
        master = ToplevelWindow(root)
        
        def changed_context(*args):
            domain_options = manager.list_problems_by_context(context_var.get())
            domain_var.set(domain_options[0])
            domain_dropdown.configure(values=domain_options)
            
        def changed_domain(*args):
            problem_info = manager.get_problem(domain_var.get())
            instance_options = problem_info.list_instances()
            instance_var.set(instance_options[0])
            instance_dropdown.configure(values=instance_options)
            
        from rddlrepository.core.manager import RDDLRepoManager
        manager = RDDLRepoManager(rebuild=True)
        
        context_options = manager.list_contexts()
        context_var = StringVar(master)
        context_var.set(context_options[0])
        context_var.trace_add('write', changed_context)
        context_dropdown = ChoiceMenu(
            master, variable=context_var, values=context_options)
        
        domain_options = manager.list_problems()
        domain_var = StringVar(master)
        domain_var.set(domain_options[0])
        domain_var.trace_add('write', changed_domain)
        domain_dropdown = ChoiceMenu(
            master, variable=domain_var, values=domain_options)
        
        problem_info = manager.get_problem(domain_options[0])
        instance_options = problem_info.list_instances()
        instance_var = StringVar(master)
        instance_var.set(instance_options[0])
        instance_dropdown = ChoiceMenu(
            master, variable=instance_var, values=instance_options)
        
        CTkLabel(master, text="Context").grid(row=0)
        CTkLabel(master, text="Domain").grid(row=1)
        CTkLabel(master, text="Instance").grid(row=2)
        e0 = context_dropdown
        e1 = domain_dropdown
        e2 = instance_dropdown
        e0.grid(row=0, column=1)
        e1.grid(row=1, column=1)
        e2.grid(row=2, column=1)
        
        def close_me():
            master.destroy()   
            
        def select_problem():
            nonlocal domain_file, inst_file, viz
            domain, instance = domain_var.get(), instance_var.get()
            manager = RDDLRepoManager()
            info = manager.get_problem(domain)
            domain_file = info.get_domain()
            inst_file = info.get_instance(instance)
            viz = info.get_visualizer()   
                     
            _pane_from_file(domain_pane, domain_editor, 'Domain', domain_file)
            _pane_from_file(inst_pane, inst_editor, 'Instance', inst_file)            
            close_me()
            domain_file, inst_file = None, None
        
        CTkButton(master, text='Load', command=select_problem).grid(
            row=3, column=0, sticky='w', pady=4)
        CTkButton(master, text='Close', command=close_me).grid(
            row=3, column=1, sticky='w', pady=4)
    
    def _pane_to_file(window, editor, caption, file_path):
        if file_path is not None: 
            with open(file_path, 'w') as new_file:
                new_file.write(editor.get(1.0, 'end'))
                new_file.close()
            window.title(f'{caption}: {os.path.basename(file_path)}')
    
    def save_domain():
        nonlocal domain_file        
        if domain_file is None:
            domain_file = fd.asksaveasfilename(initialfile='domain.rddl',
                                               defaultextension='.rddl',
                                               filetypes=[('RDDL File', '*.rddl*')])
            if domain_file == '': domain_file = None 
        _pane_to_file(domain_pane, domain_editor, 'Domain', domain_file)
        
    def save_instance():
        nonlocal inst_file        
        if inst_file is None:
            inst_file = fd.asksaveasfilename(initialfile='instance.rddl',
                                             defaultextension='.rddl',
                                             filetypes=[('RDDL File', '*.rddl*')])
            if inst_file == '': inst_file = None 
        _pane_to_file(inst_pane, inst_editor, 'Instance', inst_file)
    
    def save_domain_as():
        nonlocal domain_file        
        domain_file = None
        save_domain()
    
    def save_instance_as():
        nonlocal inst_file        
        inst_file = None
        save_instance()
        
    def exit_application():
        root.destroy()
    
    def register_domain():        
        master = ToplevelWindow(root)
        CTkLabel(master, text="Context").grid(row=0)
        CTkLabel(master, text="Domain Name").grid(row=1)
        e1 = CTkEntry(master)
        e2 = CTkEntry(master)
        e1.grid(row=0, column=1)
        e2.grid(row=1, column=1)
        
        def close_me():
            master.destroy()   
            
        def save_domain():
            from rddlrepository.core.manager import RDDLRepoManager
            manager = RDDLRepoManager()
            if e1.get() not in manager.list_contexts():
                manager.register_context(e1.get())
            manager.register_domain(e2.get(), e1.get(), domain_editor.get(1.0, 'end'))
            close_me()
            
        CTkButton(master, text='Register', command=save_domain).grid(
            row=2, column=0, sticky='w', pady=4)
        CTkButton(master, text='Close', command=close_me).grid(
            row=2, column=1, sticky='w', pady=4)
    
    def register_instance():
        master = ToplevelWindow(root)
        
        from rddlrepository.core.manager import RDDLRepoManager
        manager = RDDLRepoManager() 
        
        def changed_context(*args):
            domain_options = manager.list_problems_by_context(context_var.get())
            domain_var.set(domain_options[0])
            domain_dropdown.configure(values=domain_options)
            
        context_options = manager.list_contexts()
        context_var = StringVar(master)
        context_var.set(context_options[0])
        context_var.trace_add('write', changed_context)
        context_dropdown = ChoiceMenu(
            master, variable=context_var, values=context_options)
        
        domain_options = manager.list_problems()
        domain_var = StringVar(master)
        domain_var.set(domain_options[0])
        domain_dropdown = ChoiceMenu(
            master, variable=domain_var, values=domain_options)
        
        CTkLabel(master, text="Context").grid(row=0)
        CTkLabel(master, text="Domain").grid(row=1)
        CTkLabel(master, text="Instance").grid(row=2)
        e0 = context_dropdown
        e1 = domain_dropdown
        e2 = CTkEntry(master)
        e0.grid(row=0, column=1)
        e1.grid(row=1, column=1)
        e2.grid(row=2, column=1)
        
        def close_me():
            master.destroy()   
        
        def save_instance():
            problem_info = manager.get_problem(domain_var.get())
            problem_info.register_instance(e2.get(), inst_editor.get(1.0, 'end'))
            close_me()
        
        CTkButton(master, text='Register', command=save_instance).grid(
            row=3, column=0, sticky='w', pady=4)
        CTkButton(master, text='Close', command=close_me).grid(
            row=3, column=1, sticky='w', pady=4)
        
    # EDIT functions act on whichever editor last had the keyboard focus
    last_focused = [domain_editor]
    for editor in (domain_editor, inst_editor, policy_editor):
        editor.bind('<FocusIn>', lambda _, e=editor: last_focused.__setitem__(0, e), add='+')

    def _edit_event(event):
        editor = last_focused[0]
        editor.focus_set()
        editor._textbox.event_generate(event)  # CTkTextbox does not forward events

    def copy_text():
        _edit_event('<<Copy>>')

    def cut_text():
        _edit_event('<<Cut>>')

    def paste_text():
        _edit_event('<<Paste>>')

    # policy SELECT functions
    POLICY_FILES = [('Policy (config or Python)', '*.cfg *.py'), ('Config', '*.cfg'),
                    ('Python', '*.py')]

    def _show_error(title, error):
        print(traceback.format_exc(), file=sys.stderr)
        messagebox.showerror(title, f'{type(error).__name__}: {error}')

    def load_policy_from_file():
        policy_file = fd.askopenfilename(filetypes=POLICY_FILES)
        if policy_file:
            try:
                policy_pane.load(policy_file)
            except Exception as error:
                _show_error('Could not load policy', error)

    def save_policy_as():
        extension = policy_pane.default_extension()
        policy_file = fd.asksaveasfilename(initialfile='policy' + extension,
                                           defaultextension=extension, filetypes=POLICY_FILES)
        if policy_file:
            try:
                policy_pane.save(policy_file)
            except Exception as error:
                _show_error('Could not save policy', error)

    policy_pane.show_form('builtin')

    # policy RUN functions
    def _evaluate(record):
        nonlocal domain_file, inst_file, viz
        save_domain()
        save_instance()
        if domain_file is not None and inst_file is not None:
            editors = {'domain': domain_editor, 'instance': inst_editor}
            for editor in editors.values():
                editor.clear_error()
            try:
                build_policy, required_env_args = policy_pane.policy()
            except Exception as error:
                _show_error('Policy error', error)
                return
            message = evaluate_policy(domain_file, inst_file, build_policy, required_env_args,
                                      viz, record)
            if message is not None:
                location = locate_error(message, domain_editor.get('1.0', 'end'),
                                        inst_editor.get('1.0', 'end'))
                if location is not None:
                    editors[location.source].show_error(location.start, location.end)
    
    def evaluate():
        _evaluate(None)
    
    def record():
        save_dir = fd.askdirectory()
        if save_dir:
            _evaluate(save_dir)
        
    # domain menu
    domain_menu_file = menu.add_cascade("Domain")
    domain_menu_file_drop = MenuBarMenu(domain_menu_file)
    domain_menu_file_drop.add_option(option='New Domain', command=create_domain)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(option='Load Domain from rddlrepository...', command=open_from_dialog)
    domain_menu_file_drop.add_option(option='Load Domain from File...', command=open_domain)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(option='Save Domain', command=save_domain)
    domain_menu_file_drop.add_option(option='Save Domain As...', command=save_domain_as)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(option='Register Domain in rddlrepository...', command=register_domain)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(option='Exit', command=exit_application)
    
    # instance menu
    inst_menu_file = menu.add_cascade("Instance")
    inst_menu_file_drop = MenuBarMenu(inst_menu_file)
    inst_menu_file_drop.add_option(option='New Instance', command=create_instance)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(option='Load Instance from File...', command=open_instance)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(option='Save Instance', command=save_instance)
    inst_menu_file_drop.add_option(option='Save Instance As...', command=save_instance_as)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(option='Register Instance in rddlrepository...', command=register_instance)
    
    # edit menu, for the editor that last had the focus
    edit_menu = menu.add_cascade("Edit")
    edit_menu_drop = MenuBarMenu(edit_menu)
    edit_menu_drop.add_option(option='Copy', command=copy_text)
    edit_menu_drop.add_option(option='Cut', command=cut_text)
    edit_menu_drop.add_option(option='Paste', command=paste_text)

    # agent menu: the policy file, the built-in baselines, and running the policy
    agent_menu = menu.add_cascade("Agent")
    agent_menu_drop = MenuBarMenu(agent_menu)
    agent_menu_drop.add_option(option='Load Policy from File...', command=load_policy_from_file)
    agent_menu_drop.add_option(option='Save Policy As...', command=save_policy_as)
    agent_menu_drop.add_separator()
    for (kind, title, _) in PROVIDERS:
        agent_menu_drop.add_option(
            option=title, command=lambda kind=kind: policy_pane.show_form(kind))
    agent_menu_drop.add_separator()
    agent_menu_drop.add_option(option='Evaluate', command=evaluate)
    agent_menu_drop.add_option(option='Record', command=record)

    # view menu
    def toggle_theme():
        set_appearance_mode('light' if get_appearance_mode() == 'Dark' else 'dark')

    view_menu = menu.add_cascade("View")
    view_menu_drop = MenuBarMenu(view_menu)
    view_menu_drop.add_option(option='Toggle Light/Dark Theme', command=toggle_theme)
