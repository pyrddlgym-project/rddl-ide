import os
from difflib import SequenceMatcher
from customtkinter import CTkToplevel, CTkOptionMenu, StringVar, CTkLabel, CTkButton, CTkEntry
from customtkinter import filedialog as fd
from CTkMenuBar import CustomDropdownMenu

from rddl_ide.core.execution import evaluate_policy_fn


def closest_substring(corpus, query, case_sensitive=True):
    step = min(4, max(1, len(query) * 3 // 4 - 1))
    flex = max(1, len(query) // 3 - 1)
    
    def _match(a, b):
        return SequenceMatcher(None, a, b).ratio()

    def scan_corpus(step):
        match_values, m = [], 0
        while m + qlen - step <= len(corpus):
            match_values.append(_match(query, corpus[m: m - 1 + qlen]))
            m += step
        return match_values

    def adjust_left_right_positions():
        p_l, bp_l = pos, pos
        p_r, bp_r = pos + qlen, pos + qlen
        bmv_l = bmv_r = match_values[p_l // step]
        for f in range(flex):
            ll = _match(query, corpus[p_l - f: p_r])
            if ll > bmv_l:
                bmv_l, bp_l = ll, p_l - f
            lr = _match(query, corpus[p_l + f: p_r])
            if lr > bmv_l:
                bmv_l, bp_l = lr, p_l + f
            rl = _match(query, corpus[p_l: p_r - f])
            if rl > bmv_r:
                bmv_r, bp_r = rl, p_r - f
            rr = _match(query, corpus[p_l: p_r + f])
            if rr > bmv_r:
                bmv_r, bp_r = rr, p_r + f
        return bp_l, bp_r

    if not case_sensitive:
        query, corpus = query.lower(), corpus.lower()
    qlen = len(query)
    if flex >= qlen / 2: flex = 3
    match_values = scan_corpus(step)    
    pos = max(range(len(match_values)), key=match_values.__getitem__) * step
    return adjust_left_right_positions()


def load_policy(name):
    abs_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(abs_path, 'prefab', 'policies', name + '.py'), 'r') as file:
        content = file.read()
    return content    


def assign_menubar_functions(domain_menu, domain_window, inst_menu, inst_window, 
                             policy_menu, policy_window,
                             domain_editor, inst_editor, policy_editor):
    domain_file, inst_file, viz = None, None, None
    
    # load template RDDL
    abs_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(abs_path, 'prefab', 'domain.rddl'), 'r') as dom_txt:
        DOMAIN_TEMPLATE = dom_txt.read()
    with open(os.path.join(abs_path, 'prefab', 'instance.rddl'), 'r') as inst_txt:
        INSTANCE_TEMPLATE = inst_txt.read()
    
    # FILE functions
    def create_domain():
        global domain_file, viz
        domain_file, viz = None, None
        domain_window.title('[Domain] Untitled')
        domain_editor.delete(1.0, 'end')
        domain_editor.insert(1.0, DOMAIN_TEMPLATE)
        domain_editor.apply()
        
    def create_instance():
        global inst_file
        inst_file = None
        inst_window.title('[Instance] Untitled')
        inst_editor.delete(1.0, 'end')
        inst_editor.insert(1.0, INSTANCE_TEMPLATE)
        inst_editor.apply()
    
    def _window_from_file(window, editor, caption, file_path):
        if file_path is not None:
            window.title(f'[{caption}] {os.path.basename(file_path)}')
            editor.delete(1.0, 'end')
            with open(file_path, 'r') as new_file:
                editor.insert(1.0, new_file.read())
                new_file.close()
            editor.apply()
        
    def open_domain():
        global domain_file, viz    
        domain_file = fd.askopenfilename(defaultextension='.rddl',
                                         filetypes=[('RDDL File', '*.rddl*')])
        viz = None
        if domain_file == '': domain_file = None            
        _window_from_file(domain_window, domain_editor, 'Domain', domain_file)
    
    def open_instance():
        global inst_file        
        inst_file = fd.askopenfilename(defaultextension='.rddl',
                                       filetypes=[('RDDL File', '*.rddl*')])
        if inst_file == '': inst_file = None            
        _window_from_file(inst_window, inst_editor, 'Instance', inst_file)
    
    
    class ToplevelWindow(CTkToplevel):
    
        def __init__(self, *args, **kwargs):
            super(ToplevelWindow, self).__init__(*args, **kwargs)
            self.after(250, lambda: self.iconbitmap('icon.ico'))
        
    def open_from_dialog():
        global domain_file, inst_file, viz
        master = ToplevelWindow(domain_window)
        
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
        context_var.trace('w', changed_context)
        context_dropdown = CTkOptionMenu(
            master, variable=context_var, values=context_options)
        
        domain_options = manager.list_problems()
        domain_var = StringVar(master)
        domain_var.set(domain_options[0])
        domain_var.trace('w', changed_domain)
        domain_dropdown = CTkOptionMenu(
            master, variable=domain_var, values=domain_options)
        
        problem_info = manager.get_problem(domain_options[0])
        instance_options = problem_info.list_instances()
        instance_var = StringVar(master)
        instance_var.set(instance_options[0])
        instance_dropdown = CTkOptionMenu(
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
            master.quit()      
            master.destroy()   
            
        def select_problem():
            global domain_file, inst_file, viz
            domain, instance = domain_var.get(), instance_var.get()
            manager = RDDLRepoManager()
            info = manager.get_problem(domain)
            domain_file = info.get_domain()
            inst_file = info.get_instance(instance)
            viz = info.get_visualizer()   
                     
            _window_from_file(domain_window, domain_editor, 'Domain', domain_file)
            _window_from_file(inst_window, inst_editor, 'Instance', inst_file)            
            close_me()
            domain_file, inst_file = None, None
        
        CTkButton(master, text='Load', command=select_problem).grid(
            row=3, column=0, sticky='w', pady=4)
        CTkButton(master, text='Close', command=close_me).grid(
            row=3, column=1, sticky='w', pady=4)
    
    def _window_to_file(window, editor, caption, file_path):
        if file_path is not None: 
            with open(file_path, 'w') as new_file:
                new_file.write(editor.get(1.0, 'end'))
                new_file.close()
            window.title(f'[{caption}] {os.path.basename(file_path)}')
    
    def save_domain():
        global domain_file        
        if domain_file is None:
            domain_file = fd.asksaveasfilename(initialfile='domain.rddl',
                                               defaultextension='.rddl',
                                               filetypes=[('RDDL File', '*.rddl*')])
            if domain_file == '': domain_file = None 
        _window_to_file(domain_window, domain_editor, 'Domain', domain_file)
        
    def save_instance():
        global inst_file        
        if inst_file is None:
            inst_file = fd.asksaveasfilename(initialfile='instance.rddl',
                                             defaultextension='.rddl',
                                             filetypes=[('RDDL File', '*.rddl*')])
            if inst_file == '': inst_file = None 
        _window_to_file(inst_window, inst_editor, 'Instance', inst_file)
    
    def save_domain_as():
        global domain_file        
        domain_file = None
        save_domain()
    
    def save_instance_as():
        global inst_file        
        inst_file = None
        save_instance()
        
    def exit_application():
        domain_window.destroy() 
        inst_window.destroy() 
    
    def register_domain():        
        master = ToplevelWindow(domain_window)
        CTkLabel(master, text="Context").grid(row=0)
        CTkLabel(master, text="Domain Name").grid(row=1)
        e1 = CTkEntry(master)
        e2 = CTkEntry(master)
        e1.grid(row=0, column=1)
        e2.grid(row=1, column=1)
        
        def close_me():
            master.quit()      
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
        master = ToplevelWindow(domain_window)
        
        from rddlrepository.core.manager import RDDLRepoManager
        manager = RDDLRepoManager() 
        
        def changed_context(*args):
            domain_options = manager.list_problems_by_context(context_var.get())
            domain_var.set(domain_options[0])
            domain_dropdown.configure(values=domain_options)
            
        context_options = manager.list_contexts()
        context_var = StringVar(master)
        context_var.set(context_options[0])
        context_var.trace('w', changed_context)
        context_dropdown = CTkOptionMenu(
            master, variable=context_var, values=context_options)
        
        domain_options = manager.list_problems()
        domain_var = StringVar(master)
        domain_var.set(domain_options[0])
        domain_dropdown = CTkOptionMenu(
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
            master.quit()      
            master.destroy()   
        
        def save_instance():
            problem_info = manager.get_problem(domain_var.get())
            problem_info.register_instance(e2.get(), inst_editor.get(1.0, 'end'))
            close_me()
        
        CTkButton(master, text='Register', command=save_instance).grid(
            row=3, column=0, sticky='w', pady=4)
        CTkButton(master, text='Close', command=close_me).grid(
            row=3, column=1, sticky='w', pady=4)
        
    # EDIT functions
    def copy_domain_text():
        domain_editor.event_generate('<<Copy>>')
    
    def copy_instance_text():
        inst_editor.event_generate('<<Copy>>')
    
    def cut_domain_text():
        domain_editor.event_generate('<<Cut>>')
        
    def cut_instance_text():
        inst_editor.event_generate('<<Cut>>')
    
    def paste_domain_text():
        domain_editor.event_generate('<<Paste>>')
        
    def paste_instance_text():
        inst_editor.event_generate('<<Paste>>')
    
    # policy SELECT functions
    def _fill_policy_window(policy_name, caption):
        policy_editor.delete(1.0, 'end')
        policy_editor.insert(1.0, load_policy(policy_name))
        policy_window.title(f'[Policy] {caption}')
        policy_editor.apply()
    
    def load_policy_from_file():
        policy_file = fd.askopenfilename(defaultextension='.py',
                                         filetypes=[('Python File', '*.py*')])
        if policy_file is not None and policy_file:
            with open(policy_file, 'r') as policy_file:
                policy_editor.delete(1.0, 'end')
                policy_editor.insert(1.0, policy_file.read())
                policy_window.title('[Policy] Custom')
                policy_editor.apply()
        
    def save_policy_as():
        policy_file = fd.asksaveasfilename(initialfile='policy.py',
                                           defaultextension='.py',
                                           filetypes=[('Python File', '*.py*')])
        if policy_file is not None and policy_file:
            with open(policy_file, 'w') as new_file:
                new_file.write(policy_editor.get(1.0, 'end'))
                new_file.close()
        
    def load_noop():
        _fill_policy_window('noop', 'NoOp')
    
    load_noop()
        
    def load_random(): 
        _fill_policy_window('random', 'Random')
    
    def load_jax_slp():
        _fill_policy_window('jax_slp', 'JAX-SLP')
        
    def load_jax_replan():
        _fill_policy_window('jax_replan', 'JAX-SLP-Replan')
        
    def load_jax_drp():
        _fill_policy_window('jax_drp', 'JAX-DRP')
        
    def load_gurobi_replan():
        _fill_policy_window('gurobi_replan', 'Gurobi-SLP-Replan')
        
    def load_sb3_ppo():
        _fill_policy_window('sb3_ppo', 'StableBaselines3-PPO')
        
    # policy RUN functions
    def _evaluate(record):
        global domain_file, inst_file, viz
        save_domain()
        save_instance()
        if domain_file is not None and inst_file is not None:
            domain_editor.tag_delete('showerror')
            query = evaluate_policy_fn(domain_file, inst_file, policy_editor, viz, record)
            if query is not None:
                corpus = domain_editor.get(1.0, 'end')
                start, end = closest_substring(corpus, query)                
                domain_editor.tag_add('showerror', f'1.0+{start}c', f'1.0+{end}c')
                domain_editor.tag_config('showerror', background='yellow')
    
    def evaluate():
        _evaluate(None)
    
    def record():
        _evaluate(fd.askdirectory())
        
    # domain menu bars
    domain_menu_file = domain_menu.add_cascade("File")
    domain_menu_file_drop = CustomDropdownMenu(widget=domain_menu_file, font=("Roboto", 14))
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
    
    domain_menu_edit = domain_menu.add_cascade("Edit")
    domain_menu_edit_drop = CustomDropdownMenu(widget=domain_menu_edit, font=("Roboto", 14))
    domain_menu_edit_drop.add_option(option='Copy', command=copy_domain_text)
    domain_menu_edit_drop.add_option(option='Cut', command=cut_domain_text)
    domain_menu_edit_drop.add_option(option='Paste', command=paste_domain_text)
    
    # instance menu bar
    inst_menu_file = inst_menu.add_cascade("File")
    inst_menu_file_drop = CustomDropdownMenu(widget=inst_menu_file, font=("Roboto", 14))
    inst_menu_file_drop.add_option(option='New Instance', command=create_instance)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(option='Load Instance from File...', command=open_instance)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(option='Save Instance', command=save_instance)
    inst_menu_file_drop.add_option(option='Save Instance As...', command=save_instance_as)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(option='Register Instance in rddlrepository...', command=register_instance)
    
    # instance edit menu
    inst_menu_edit = inst_menu.add_cascade("Edit")
    inst_menu_edit_drop = CustomDropdownMenu(widget=inst_menu_edit, font=("Roboto", 14))
    inst_menu_edit_drop.add_option(option='Copy', command=copy_instance_text)
    inst_menu_edit_drop.add_option(option='Cut', command=cut_instance_text)
    inst_menu_edit_drop.add_option(option='Paste', command=paste_instance_text)
    
    # policy file menu
    policy_file_menu = policy_menu.add_cascade("File")
    policy_file_menu_drop = CustomDropdownMenu(widget=policy_file_menu, font=("Roboto", 14))
    policy_file_menu_drop.add_option(option='Load Policy from File...', command=load_policy_from_file)
    policy_file_menu_drop.add_option(option='Save Policy As...', command=save_policy_as)
    
    # policy load menu
    policy_load_menu = policy_menu.add_cascade("Baseline")
    policy_load_menu_drop = CustomDropdownMenu(widget=policy_load_menu, font=("Roboto", 14))
    policy_load_menu_drop.add_option(option='No-Op', command=load_noop)
    policy_load_menu_drop.add_option(option='Random', command=load_random)
    policy_load_menu_drop.add_separator()
    policy_load_menu_drop.add_option(option='JAX Planner (SLP)', command=load_jax_slp)
    policy_load_menu_drop.add_option(option='JAX Planner (SLP+Replan)', command=load_jax_replan)
    policy_load_menu_drop.add_option(option='JAX Planner (DRP)', command=load_jax_drp)
    policy_load_menu_drop.add_separator()
    policy_load_menu_drop.add_option(option='Gurobi Planner (SLP+Replan)', command=load_gurobi_replan)
    policy_load_menu_drop.add_separator()
    policy_load_menu_drop.add_option(option='Stable-Baselines3 (PPO)', command=load_sb3_ppo)
    
    # policy run menu
    policy_run_menu = policy_menu.add_cascade("Run")
    policy_run_menu_drop = CustomDropdownMenu(widget=policy_run_menu, font=("Roboto", 14))
    policy_run_menu_drop.add_option(option='Evaluate', command=evaluate)
    policy_run_menu_drop.add_option(option='Record', command=record)