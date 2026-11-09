import os
import sys
import traceback
from tkinter import messagebox
from customtkinter import StringVar, CTkEntry
from customtkinter import get_appearance_mode, set_appearance_mode
from customtkinter import filedialog as fd

from rddl_ide.core.dialog import Dialog
from rddl_ide.core.errorlocation import locate_error
from rddl_ide.core.execution import evaluate_policy
from rddl_ide.core.icons import RECORD_COLOR, IconButton
from rddl_ide.core.popup import ChoiceMenu, MenuBarMenu
from rddl_ide.core.settings.registry import PROVIDERS
from rddl_ide.core.statusbar import RunProgress
from rddl_ide.core import textfile


def assign_menubar_functions(menu, root, domain_pane, inst_pane, policy_pane,
                             domain_editor, inst_editor, status_bar):
    policy_editor = policy_pane.text
    domain_file, inst_file, viz = None, None, None
    
    # load template RDDL
    abs_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(
            abs_path, 'prefab', 'domain.rddl'), encoding='utf-8') as dom_txt:
        DOMAIN_TEMPLATE = dom_txt.read()
    with open(os.path.join(
            abs_path, 'prefab', 'instance.rddl'), encoding='utf-8') as inst_txt:
        INSTANCE_TEMPLATE = inst_txt.read()
    
    # FILE functions
    def create_domain():
        nonlocal domain_file, viz
        domain_file, viz = None, None
        domain_pane.title('Domain: Untitled')
        domain_editor.set_text(DOMAIN_TEMPLATE)
        
    def create_instance():
        nonlocal inst_file
        inst_file = None
        inst_pane.title('Instance: Untitled')
        inst_editor.set_text(INSTANCE_TEMPLATE)
    
    def _pane_from_file(window, editor, caption, file_path):
        if file_path is not None:
            window.title(f'{caption}: {os.path.basename(file_path)}')
            editor.set_text(*textfile.read(file_path))
        
    def open_domain():
        nonlocal domain_file, viz    
        domain_file = fd.askopenfilename(
            defaultextension='.rddl', filetypes=[('RDDL File', '*.rddl*')])
        viz = None
        if domain_file == '': domain_file = None            
        _pane_from_file(domain_pane, domain_editor, 'Domain', domain_file)
    
    def open_instance():
        nonlocal inst_file        
        inst_file = fd.askopenfilename(
            defaultextension='.rddl', filetypes=[('RDDL File', '*.rddl*')])
        if inst_file == '': inst_file = None            
        _pane_from_file(inst_pane, inst_editor, 'Instance', inst_file)
    
    
    def open_from_dialog():
        nonlocal domain_file, inst_file, viz
        dialog = Dialog(root, 'Load from rddlrepository')
        master = dialog.body
        
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
        
        dialog.field('Context', context_dropdown)
        dialog.field('Domain', domain_dropdown)
        dialog.field('Instance', instance_dropdown)

        def close_me():
            dialog.destroy()

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
        
        dialog.buttons('Load', select_problem)
    
    def _pane_to_file(window, editor, caption, file_path):
        if file_path is not None: 
            editor.file_format = textfile.write(
                file_path, editor.content(), editor.file_format)
            status_bar.update_position()
            window.title(f'{caption}: {os.path.basename(file_path)}')
    
    def save_domain():
        nonlocal domain_file        
        if domain_file is None:
            domain_file = fd.asksaveasfilename(
                initialfile='domain.rddl', defaultextension='.rddl',
                filetypes=[('RDDL File', '*.rddl*')])
            if domain_file == '': domain_file = None 
        _pane_to_file(domain_pane, domain_editor, 'Domain', domain_file)
        
    def save_instance():
        nonlocal inst_file        
        if inst_file is None:
            inst_file = fd.asksaveasfilename(
                initialfile='instance.rddl', defaultextension='.rddl',
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
        
    active_run = None
    close_after_run = False

    def exit_application():
        nonlocal close_after_run
        if active_run is not None:
            close_after_run = True
            active_run.stop()
        else:
            root.destroy()

    def stop_run():
        if active_run is not None:
            active_run.stop()

    buttons_changed = []
    
    root.protocol('WM_DELETE_WINDOW', exit_application)
    
    def register_domain():
        dialog = Dialog(root, 'Register domain in rddlrepository')
        e1 = dialog.field('Context', CTkEntry(dialog.body))
        e2 = dialog.field('Domain name', CTkEntry(dialog.body))

        def close_me():
            dialog.destroy()

        def save_domain():
            from rddlrepository.core.manager import RDDLRepoManager
            manager = RDDLRepoManager()
            if e1.get() not in manager.list_contexts():
                manager.register_context(e1.get())
            manager.register_domain(e2.get(), e1.get(), domain_editor.get(1.0, 'end'))
            close_me()
            
        dialog.buttons('Register', save_domain)
    
    def register_instance():
        dialog = Dialog(root, 'Register instance in rddlrepository')
        master = dialog.body
        
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
        
        dialog.field('Context', context_dropdown)
        dialog.field('Domain', domain_dropdown)
        e2 = dialog.field('Instance name', CTkEntry(master))

        def close_me():
            dialog.destroy()
        
        def save_instance():
            problem_info = manager.get_problem(domain_var.get())
            problem_info.register_instance(e2.get(), inst_editor.content())
            close_me()
        
        dialog.buttons('Register', save_instance)
        
    # EDIT functions act on whichever editor last had the keyboard focus
    last_focused = [domain_editor]
    for editor in (domain_editor, inst_editor, policy_editor):
        editor.bind(
            '<FocusIn>', lambda _, e=editor: last_focused.__setitem__(0, e), add='+')
        status_bar.track(editor)
    policy_pane.changed.append(status_bar.update_position)
    
    def _edit_event(event):
        editor = last_focused[0]
        editor.focus_set()
        editor._textbox.event_generate(event)
        
    def undo_text():
        _edit_event('<<Undo>>')
        last_focused[0].apply()
        
    def redo_text():
        _edit_event('<<Redo>>')
        last_focused[0].apply()

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
        policy_file = fd.asksaveasfilename(
            initialfile='policy' + extension,
            defaultextension=extension, filetypes=POLICY_FILES)
        if policy_file:
            try:
                policy_pane.save(policy_file)
            except Exception as error:
                _show_error('Could not save policy', error)

    policy_pane.show_form('builtin')

    # trained WEIGHTS, of the baselines that have them, e.g. JaxPlan (offline)
    trained = None
    
    def load_weights():
        provider = policy_pane.provider
        if provider is None or provider.weight_files is None:
            messagebox.showinfo(
                'Load Weights', 'The selected policy has no weights to '
                                'load. JaxPlan (offline) has.')
            return
        path = fd.askopenfilename(filetypes=provider.weight_files)
        if path:
            provider.load_weights(policy_pane.state, path)
            policy_pane.body.render()
            status_bar.show(f'Loaded {os.path.basename(path)}: the next run uses these '
                            f'weights instead of training')

    def save_weights():
        if trained is None:
            messagebox.showinfo('Save Trained Weights', 'No weights were trained yet: '
                                'evaluate a JaxPlan (offline) policy first.')
            return
        (provider, policy) = trained
        path = fd.asksaveasfilename(
            initialfile='weights.pickle', defaultextension='.pickle',
            filetypes=provider.weight_files)
        if path:
            try:
                provider.save_weights(policy, path)
                status_bar.show(f'Saved the trained weights to {os.path.basename(path)}')
            except Exception as error:
                _show_error('Could not save weights', error)

    # policy RUN functions
    def _evaluate(record):
        nonlocal domain_file, inst_file, viz, active_run, trained
        if active_run is not None:
            return
        save_domain()
        save_instance()
        if domain_file is not None and inst_file is not None:
            editors = {'domain': domain_editor, 'instance': inst_editor}
            for editor in editors.values():
                editor.clear_error()
            progress = RunProgress(status_bar)
            try:
                build_policy, required_env_args = policy_pane.policy(progress)
            except Exception as error:
                _show_error('Policy error', error)
                return
            provider = policy_pane.provider
            active_run = progress
            for update in buttons_changed:
                update()
            try:
                message = evaluate_policy(
                    domain_file, inst_file, build_policy, required_env_args, viz, record, 
                    progress)
            finally:
                active_run = None
                if progress.policy is not None and provider is not None and \
                        provider.weight_files is not None:
                    trained = (provider, progress.policy)
                for update in buttons_changed:
                    update()
            if close_after_run:
                root.destroy()
                return
            if progress.stopped:
                progress.show_stopped()
                return
            if message is not None:
                location = locate_error(
                    message, domain_editor.get('1.0', 'end'),
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
    domain_menu_file_drop.add_option(
        option='Load Domain from rddlrepository...', command=open_from_dialog)
    domain_menu_file_drop.add_option(
        option='Load Domain from File...', command=open_domain)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(option='Save Domain', command=save_domain)
    domain_menu_file_drop.add_option(option='Save Domain As...', command=save_domain_as)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(
        option='Register Domain in rddlrepository...', command=register_domain)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(option='Exit', command=exit_application)
    
    # instance menu
    inst_menu_file = menu.add_cascade("Instance")
    inst_menu_file_drop = MenuBarMenu(inst_menu_file)
    inst_menu_file_drop.add_option(option='New Instance', command=create_instance)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(
        option='Load Instance from File...', command=open_instance)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(option='Save Instance', command=save_instance)
    inst_menu_file_drop.add_option(option='Save Instance As...', command=save_instance_as)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(
        option='Register Instance in rddlrepository...', command=register_instance)
    
    # edit menu, for the editor that last had the focus
    edit_menu = menu.add_cascade("Edit")
    edit_menu_drop = MenuBarMenu(edit_menu)
    edit_menu_drop.add_option(option='Undo', command=undo_text)
    edit_menu_drop.add_option(option='Redo', command=redo_text)
    edit_menu_drop.add_separator()
    edit_menu_drop.add_option(option='Copy', command=copy_text)
    edit_menu_drop.add_option(option='Cut', command=cut_text)
    edit_menu_drop.add_option(option='Paste', command=paste_text)

    # agent menu: the policy file, the built-in baselines, and running the policy
    agent_menu = menu.add_cascade("Agent")
    agent_menu_drop = MenuBarMenu(agent_menu)
    agent_menu_drop.add_option(
        option='Load Policy from File...', command=load_policy_from_file)
    agent_menu_drop.add_option(option='Save Policy As...', command=save_policy_as)
    agent_menu_drop.add_option(option='Load Weights...', command=load_weights)
    agent_menu_drop.add_option(option='Save Trained Weights...', command=save_weights)
    agent_menu_drop.add_separator()
    for (kind, title, _) in PROVIDERS:
        agent_menu_drop.add_option(
            option=title, command=lambda kind=kind: policy_pane.show_form(kind))
    agent_menu_drop.add_separator()
    agent_menu_drop.add_option(option='Evaluate', command=evaluate)
    agent_menu_drop.add_option(option='Record', command=record)
    agent_menu_drop.add_option(option='Stop', command=stop_run)

    # view menu
    def toggle_theme():
        set_appearance_mode('light' if get_appearance_mode() == 'Dark' else 'dark')

    view_menu = menu.add_cascade("View")
    view_menu_drop = MenuBarMenu(view_menu)
    view_menu_drop.add_option(option='Toggle Light/Dark Theme', command=toggle_theme)

    # buttons: on the right of the menu bar and of the header of each pane
    menu.grid_columnconfigure(menu.num, weight=1)
    theme_button = IconButton(
        menu, 'moon', 'Toggle light/dark theme', toggle_theme, dark_name='sun')
    theme_button.grid(row=0, column=menu.num + 1, padx=(0, 6), pady=2)

    for (header, noun, commands) in (
            (domain_pane.header, 'domain',
             (create_domain, open_domain, save_domain, save_domain_as)),
            (inst_pane.header, 'instance',
             (create_instance, open_instance, save_instance, save_instance_as))):
        for (icon, tooltip, command) in zip(
                ('new', 'load', 'save', 'save_as'),
                (f'New {noun}', f'Load {noun} from file', f'Save {noun}',
                 f'Save {noun} as'), commands):
            header.add_button(icon, tooltip, command)

    policy_header = policy_pane.header
    policy_header.add_button('load', 'Load policy from file', load_policy_from_file)
    policy_header.add_button('save', 'Save policy as', save_policy_as)
    policy_header.add_gap()
    load_weights_button = policy_header.add_button(
        'load_weights', 'Load trained weights', load_weights)
    save_weights_button = policy_header.add_button(
        'save_weights', 'Save trained weights', save_weights)
    policy_header.add_gap()
    run_buttons = [
        policy_header.add_button('run', 'Evaluate', evaluate),
        policy_header.add_button('record', 'Record', record, colors=RECORD_COLOR)
    ]
    stop_button = policy_header.add_button('stop', 'Stop', stop_run)

    def update_buttons():
        running = active_run is not None
        for button in run_buttons:
            button.set_enabled(not running)
        stop_button.set_enabled(running)
        provider = policy_pane.provider
        load_weights_button.set_enabled(
            not running and provider is not None and provider.weight_files is not None)
        save_weights_button.set_enabled(not running and trained is not None)

    buttons_changed.append(update_buttons)
    policy_pane.changed.append(update_buttons)
    update_buttons()
