import os
import sys
import traceback
from tkinter import TclError, messagebox
from customtkinter import (
    StringVar, CTkButton, CTkCheckBox, CTkEntry, CTkFrame, ThemeManager
)
from customtkinter import get_appearance_mode, set_appearance_mode
from customtkinter import filedialog as fd

from rddl_ide.core.checking import check
from rddl_ide.core.dialog import Dialog
from rddl_ide.core.findbar import FindBar
from rddl_ide.core.errorlocation import locate_error, strip_ansi
from rddl_ide.core.execution import VISUALIZERS, RunOptions, evaluate_policy
from rddl_ide.core.graphview import DependencyWindow
from rddl_ide.core.grounding import ground
from rddl_ide.core.icons import RECORD_COLOR, IconButton
from rddl_ide.core.outline import definitions, line_column
from rddl_ide.core.popup import ChoiceMenu, MenuBarMenu
from rddl_ide.core.settings.registry import PROVIDERS
from rddl_ide.core.shortcuts import MAC, WINDOWS, Shortcuts, label
from rddl_ide.core.statusbar import RunProgress, RunStopped
from rddl_ide.core.stepperview import StepperWindow
from rddl_ide.core.stepping import Stepper
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
        if not confirm_discard('domain'):
            return
        domain_file, viz = None, None
        domain_pane.title('Domain: Untitled')
        domain_editor.set_text(DOMAIN_TEMPLATE)
        
    def create_instance():
        nonlocal inst_file
        if not confirm_discard('instance'):
            return
        inst_file = None
        inst_pane.title('Instance: Untitled')
        inst_editor.set_text(INSTANCE_TEMPLATE)
    
    def _pane_from_file(window, editor, caption, file_path):
        if file_path is not None:
            window.title(f'{caption}: {os.path.basename(file_path)}')
            editor.set_text(*textfile.read(file_path))
        
    def open_domain():
        nonlocal domain_file, viz
        if not confirm_discard('domain'):
            return
        path = fd.askopenfilename(
            defaultextension='.rddl', filetypes=[('RDDL File', '*.rddl*')])
        if path:
            domain_file, viz = path, None
            _pane_from_file(domain_pane, domain_editor, 'Domain', domain_file)

    def open_instance():
        nonlocal inst_file
        if not confirm_discard('instance'):
            return
        path = fd.askopenfilename(
            defaultextension='.rddl', filetypes=[('RDDL File', '*.rddl*')])
        if path:
            inst_file = path
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
            if not confirm_discard('domain', 'instance'):
                return
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
            editor.mark_saved()
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
    
    def ground_problem():
        '''Replaces the domain and instance by their grounded versions, as new files,
        in one step that undo takes back in each editor.'''
        nonlocal domain_file, inst_file, viz
        if not confirm_discard('domain', 'instance'):
            return
        for editor in (domain_editor, inst_editor):
            editor.clear_error()
        status_bar.show('Grounding the domain and instance...')
        status_bar.update_idletasks()
        try:
            (domain, instance) = ground(domain_editor.content(), inst_editor.content())
        except Exception as error:
            status_bar.show('Grounding failed')
            _show_error('Could not ground the domain and instance', error)
            highlight_error(str(error))
            return
        domain_file, inst_file, viz = None, None, None
        for (editor, text) in ((domain_editor, domain), (inst_editor, instance)):
            editor.replace_text(text)
            editor.mark_saved(False)
        domain_pane.title('Domain: Untitled (grounded)')
        inst_pane.title('Instance: Untitled (grounded)')
        status_bar.show('Grounded the domain and instance')

    def save_instance_as():
        nonlocal inst_file
        inst_file = None
        save_instance()

    def highlight_error(message):
        '''Marks the part of the domain or instance a pyRDDLGym error points to.'''
        location = locate_error(message, domain_editor.content(), inst_editor.content())
        if location is not None:
            {'domain': domain_editor, 'instance': inst_editor}[location.source].show_error(
                location.start, location.end)

    def check_problem():
        '''Parses and compiles the domain and instance as they are in the editors.'''
        if active_run is not None:
            return
        for editor in (domain_editor, inst_editor):
            editor.clear_error()
        status_bar.show('Checking the domain and instance...')
        status_bar.update_idletasks()
        try:
            summary = check(domain_editor.content(), inst_editor.content())
        except Exception as error:
            status_bar.show(f'Check failed: {type(error).__name__}')
            _show_error('Check found an error', error)
            highlight_error(str(error))
            return
        status_bar.show(summary)

    # UNSAVED changes: asked about before they are replaced or the window is closed
    def confirm_discard(*names) -> bool:
        '''Offers to save the unsaved changes of the named panes.'''
        for name in names:
            (pane, modified, save) = {
                'domain': (domain_pane, domain_editor.modified, save_domain),
                'instance': (inst_pane, inst_editor.modified, save_instance),
                'policy': (policy_pane, policy_pane.code_modified, save_policy_as),
            }[name]
            if not modified():
                continue
            shown = pane.header.label.cget('text') or 'Untitled'
            answer = messagebox.askyesnocancel(
                'Unsaved changes', 
                f'The {name} ({shown}) has unsaved changes.\n\nSave them first?', 
                parent=root)
            if answer is None:
                return False
            if answer:
                save()
                if modified():
                    return False
        return True
        
    active_run = None
    close_after_run = False

    def exit_application():
        nonlocal close_after_run
        if not confirm_discard('domain', 'instance', 'policy'):
            return
        close_after_run = True
        finish_exit()

    def finish_exit():
        '''Closes the stepper and stops the run going, if any, before the window.'''
        if stepper_window is not None:
            stepper_window.close()
        elif active_run is not None:
            active_run.stop()
        else:
            root.destroy()

    def stop_run():
        if stepper_window is not None:
            stepper_window.stop()
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
        messagebox.showerror(title, strip_ansi(f'{type(error).__name__}: {error}'))

    def load_policy_from_file():
        if not confirm_discard('policy'):
            return
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
                if policy_pane.mode == 'code':
                    policy_editor.mark_saved()
            except Exception as error:
                _show_error('Could not save policy', error)

    def choose_policy(kind):
        if confirm_discard('policy'):
            policy_pane.show_form(kind)

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
                    progress, run_options)
            finally:
                active_run = None
                if progress.policy is not None and provider is not None and \
                        provider.weight_files is not None:
                    trained = (provider, progress.policy)
                for update in buttons_changed:
                    update()
            if close_after_run:
                finish_exit()
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

    # STEPPING through an episode of the policy, in a window of its own
    stepper_window = None

    def step_through():
        '''Opens the stepper for the policy shown, or takes a step in the one open.'''
        nonlocal active_run, trained, stepper_window
        if stepper_window is not None:
            stepper_window.lift()
            stepper_window.step()
            return
        if active_run is not None:
            return
        save_domain()
        save_instance()
        if domain_file is None or inst_file is None:
            return
        for editor in (domain_editor, inst_editor):
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
        stepper = None
        try:
            progress.note('Preparing the environment and the policy...')
            stepper = Stepper(domain_file, inst_file, build_policy, required_env_args,
                              viz, run_options, progress)
        except RunStopped:
            pass
        except Exception as error:
            status_bar.show(f'Could not start stepping: {type(error).__name__}')
            _show_error('pyRDDLGym error', error)
            highlight_error(str(error))
        finally:
            active_run = None
            if progress.policy is not None and provider is not None and \
                    provider.weight_files is not None:
                trained = (provider, progress.policy)
            for update in buttons_changed:
                update()
        if stepper is None or close_after_run:
            if stepper is not None:
                stepper.close()
            if close_after_run:
                finish_exit()
            elif progress.stopped:
                progress.show_stopped()
            return

        def busy(running):
            nonlocal active_run
            if running:
                active_run = progress
            elif active_run is progress:
                active_run = None
            for update in buttons_changed:
                update()

        def closed(note):
            nonlocal stepper_window
            stepper_window = None
            try:
                status_bar.show('Stopped stepping' + note)
            except TclError:
                pass
            if close_after_run:
                root.after_idle(finish_exit)

        status_bar.show('Stepping through an episode')
        stepper_window = StepperWindow(
            root, stepper, progress, f'Step Through: {stepper.model.domain_name}',
            busy=busy, allowed=lambda: active_run is None, on_error=highlight_error,
            on_close=closed)

    run_options = RunOptions()

    def edit_run_options():
        '''Asks for the number of episodes, the seed, the visualizer, the simulation log
        and whether action constraints are enforced, for the runs that follow.'''
        dialog = Dialog(root, 'Run Options')
        palette = ThemeManager.theme['Palette']
        episodes = dialog.field('Episodes', CTkEntry(dialog.body))
        episodes.insert(0, str(run_options.episodes))
        seed = dialog.field('Seed', CTkEntry(dialog.body, placeholder_text='Random'))
        if run_options.seed is not None:
            seed.insert(0, str(run_options.seed))
        visualizer = StringVar(dialog, VISUALIZERS[run_options.visualizer])
        dialog.field('Visualizer', ChoiceMenu(
            dialog.body, variable=visualizer, values=list(VISUALIZERS.values())))
        log_row = dialog.field(
            'Simulation log', CTkFrame(dialog.body, fg_color='transparent'))
        log_file = CTkEntry(log_row, width=100, placeholder_text='None')
        log_file.pack(side='left', fill='x', expand=True)
        if run_options.log_file:
            log_file.insert(0, run_options.log_file)

        def browse():
            path = fd.asksaveasfilename(
                parent=dialog, initialfile='simulation_log.csv', defaultextension='.csv',
                filetypes=[('CSV File', '*.csv')])
            if path:
                log_file.delete(0, 'end')
                log_file.insert(0, path)

        CTkButton(log_row, text='Browse...', width=0, fg_color='transparent',
                  hover_color=palette['hover'], text_color=palette['text'],
                  border_width=1, border_color=palette['field_border'],
                  command=browse).pack(side='left', padx=(6, 0))
        enforce = dialog.field('Action constraints', CTkCheckBox(
            dialog.body, text='Stop the run when one is violated', checkbox_width=18,
            checkbox_height=18, border_width=1))
        if run_options.enforce_constraints:
            enforce.select()

        def whole_number(entry, minimum=None):
            '''(valid, the integer typed or None if left empty where allowed).'''
            text = entry.get().strip()
            try:
                value = None if text == '' and minimum is None else int(text)
                if value is None or minimum is None or value >= minimum:
                    entry.configure(border_color=palette['field_border'])
                    return (True, value)
            except ValueError:
                pass
            entry.configure(border_color=RECORD_COLOR)
            return (False, None)

        def save():
            nonlocal run_options
            (episodes_ok, count) = whole_number(episodes, 1)
            (seed_ok, seed_value) = whole_number(seed)
            if not (episodes_ok and seed_ok):
                return
            chosen = next(key for (key, name) in VISUALIZERS.items()
                          if name == visualizer.get())
            run_options = RunOptions(count, seed_value, chosen,
                                     log_file.get().strip() or None, bool(enforce.get()))
            dialog.destroy()
            status_bar.show(describe_run_options())

        dialog.buttons('Save', save)

    def describe_run_options():
        options = run_options
        parts = [f'{options.episodes} episode{"s" if options.episodes > 1 else ""}',
                 'random seed' if options.seed is None else f'seed {options.seed}',
                 f'{VISUALIZERS[options.visualizer]} visualizer']
        if options.log_file:
            parts.append(f'log to {os.path.basename(options.log_file)}')
        if options.enforce_constraints:
            parts.append('action constraints enforced')
        return 'Run options: ' + ', '.join(parts)

    # DEPENDENCY graph of the domain
    graph_window = None

    def show_dependencies():
        nonlocal graph_window
        if graph_window is not None and graph_window.winfo_exists():
            graph_window.refresh()
            graph_window.deiconify()
            graph_window.lift()
            graph_window.focus_force()
            return
        graph_window = DependencyWindow(
            root, lambda: (domain_editor.content(), inst_editor.content()),
            go_to_definition)

    def go_to_definition(name):
        '''Selects where the domain defines the fluent (its CPF, else its declaration)
        or the reward.'''
        text = domain_editor.content()
        found = definitions(text)
        if name == 'reward':
            offset = found.get('', {}).get('reward')
        else:
            offset = found.get('cpfs', {}).get(name, found.get('cdfs', {}).get(name))
            if offset is None:
                offset = found.get('pvariables', {}).get(name.rstrip("'"))
        if offset is None:
            status_bar.show(f'Could not find where the domain defines {name}')
            return
        start = line_column(text, offset)
        domain_editor.tag_remove('sel', '1.0', 'end')
        domain_editor.tag_add('sel', start, f'{start}+{len(name)}c')
        domain_editor.mark_set('insert', start)
        domain_editor.see(start)
        domain_editor.focus_set()
        
    # FIND, replace and go to line, in the editor in use
    find_bars = {}

    last_pane = 'domain'

    def active_pane():
        '''The pane ('domain', 'instance' or 'policy') the keyboard focus is in, else
        the pane it was last in.'''
        try:
            focus = root.focus_get()
        except KeyError:
            focus = None
        path = str(focus) if focus is not None else ''
        for (name, pane) in (('domain', domain_pane), ('instance', inst_pane),
                             ('policy', policy_pane)):
            if path.startswith(str(pane) + '.'):
                return name
        return last_pane

    def show_active_pane(_=None):
        '''Underlines the header of the active pane, which the shortcuts act on.'''
        nonlocal last_pane
        try:
            last_pane = active_pane()
            for (name, pane) in (('domain', domain_pane), ('instance', inst_pane),
                                 ('policy', policy_pane)):
                pane.header.set_active(name == last_pane)
        except TclError:
            pass

    root.bind_all('<FocusIn>', lambda _: root.after_idle(show_active_pane), add='+')
    show_active_pane()

    def edit_target():
        '''The editor that find and go to line act on: that of the pane in use, or the
        domain's while the policy pane shows a form.'''
        name = active_pane()
        if name == 'policy' and policy_pane.mode != 'code':
            name = 'domain'
        return {'domain': domain_editor, 'instance': inst_editor,
                'policy': policy_editor}[name]

    def find_bar(editor):
        if editor not in find_bars:
            find_bars[editor] = FindBar(editor, editor.gutter)
        return find_bars[editor]

    def find_text():
        find_bar(edit_target()).show()

    def find_and_replace():
        find_bar(edit_target()).show(replace=True)

    def go_to_line():
        editor = edit_target()
        last = int(editor.index('end-1c').split('.')[0])
        dialog = Dialog(root, 'Go to Line')
        entry = dialog.field(f'Line (1–{last})', CTkEntry(dialog.body))
        entry.insert(0, editor.index('insert').split('.')[0])

        def go():
            try:
                line = int(entry.get().strip())
            except ValueError:
                entry.configure(border_color=RECORD_COLOR)
                return
            dialog.destroy()
            index = f'{max(1, min(line, last))}.0'
            editor.mark_set('insert', index)
            editor.tag_remove('sel', '1.0', 'end')
            editor.see(index)
            editor.focus_set()

        dialog.buttons('Go', go)
        dialog.after(150, lambda: (entry.focus_set(), entry.select_range(0, 'end')))

    # VIEW functions
    def toggle_theme():
        set_appearance_mode('light' if get_appearance_mode() == 'Dark' else 'dark')

    word_wrap = False

    def toggle_word_wrap():
        '''Wraps long lines at the edge of the domain, instance and policy editors, or
        not; the button stays shaded while they are wrapped.'''
        nonlocal word_wrap
        word_wrap = not word_wrap
        for editor in (domain_editor, inst_editor, policy_editor):
            editor.configure(wrap='word' if word_wrap else 'none')
        wrap_button.configure(fg_color=ThemeManager.theme['Palette']['hover']
                              if word_wrap else 'transparent')

    # keyboard SHORTCUTS: those of files act on the pane in use (e.g. Ctrl+S saves the
    # domain while editing it); undo, redo, cut, copy and paste are Tk's own
    shortcuts = Shortcuts(root)
    for editor in (domain_editor, inst_editor, policy_editor):
        shortcuts.attach(editor)

    def per_pane(domain_command, instance_command, policy_command=None):
        def command():
            chosen = {'domain': domain_command, 'instance': instance_command,
                      'policy': policy_command}[active_pane()]
            if chosen is not None:
                chosen()
        return command

    NEW = shortcuts.add(per_pane(create_domain, create_instance), 'n', control=True)
    OPEN = shortcuts.add(per_pane(open_domain, open_instance, load_policy_from_file),
                         'o', control=True)
    SAVE = shortcuts.add(per_pane(save_domain, save_instance, save_policy_as),
                         's', control=True)
    SAVE_AS = shortcuts.add(per_pane(save_domain_as, save_instance_as, save_policy_as),
                            's', control=True, shift=True)
    FIND = shortcuts.add(find_text, 'f', control=True)
    if MAC:  # where Cmd+H hides the app
        REPLACE = shortcuts.add(find_and_replace, 'f', control=True, alt=True)
        GOTO = shortcuts.add(go_to_line, 'l', control=True)
    else:
        REPLACE = shortcuts.add(find_and_replace, 'h', control=True)
        GOTO = shortcuts.add(go_to_line, 'g', control=True)
    CHECK = shortcuts.add(check_problem, 'F7')
    RUN = shortcuts.add(evaluate, 'F5')
    STEP = shortcuts.add(step_through, 'F10')
    STOP = shortcuts.add(stop_run, 'F5', shift=True)
    WRAP = shortcuts.add(toggle_word_wrap, 'z', alt=True)
    UNDO = label('z', control=True)
    REDO = label('y', control=True) if WINDOWS else label('z', control=True, shift=True)
    (CUT, COPY, PASTE) = (label(key, control=True) for key in 'xcv')

    # domain menu
    domain_menu_file = menu.add_cascade("Domain")
    domain_menu_file_drop = MenuBarMenu(domain_menu_file)
    domain_menu_file_drop.add_option('New Domain', create_domain, NEW)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(
        'Load Domain from rddlrepository...', open_from_dialog)
    domain_menu_file_drop.add_option('Load Domain from File...', open_domain, OPEN)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option('Save Domain', save_domain, SAVE)
    domain_menu_file_drop.add_option('Save Domain As...', save_domain_as, SAVE_AS)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option('Check Domain and Instance', check_problem, CHECK)
    domain_menu_file_drop.add_option('Ground Domain and Instance', ground_problem)
    domain_menu_file_drop.add_option('Show Dependency Graph', show_dependencies)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option(
        'Register Domain in rddlrepository...', register_domain)
    domain_menu_file_drop.add_separator()
    domain_menu_file_drop.add_option('Exit', exit_application)

    # instance menu
    inst_menu_file = menu.add_cascade("Instance")
    inst_menu_file_drop = MenuBarMenu(inst_menu_file)
    inst_menu_file_drop.add_option('New Instance', create_instance, NEW)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option('Load Instance from File...', open_instance, OPEN)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option('Save Instance', save_instance, SAVE)
    inst_menu_file_drop.add_option('Save Instance As...', save_instance_as, SAVE_AS)
    inst_menu_file_drop.add_separator()
    inst_menu_file_drop.add_option(
        'Register Instance in rddlrepository...', register_instance)

    # edit menu, for the editor that last had the focus
    edit_menu = menu.add_cascade("Edit")
    edit_menu_drop = MenuBarMenu(edit_menu)
    edit_menu_drop.add_option('Undo', undo_text, UNDO)
    edit_menu_drop.add_option('Redo', redo_text, REDO)
    edit_menu_drop.add_separator()
    edit_menu_drop.add_option('Cut', cut_text, CUT)
    edit_menu_drop.add_option('Copy', copy_text, COPY)
    edit_menu_drop.add_option('Paste', paste_text, PASTE)
    edit_menu_drop.add_separator()
    edit_menu_drop.add_option('Find...', find_text, FIND)
    edit_menu_drop.add_option('Replace...', find_and_replace, REPLACE)
    edit_menu_drop.add_option('Go to Line...', go_to_line, GOTO)

    # agent menu: the policy file, the built-in baselines, and running the policy
    agent_menu = menu.add_cascade("Agent")
    agent_menu_drop = MenuBarMenu(agent_menu)
    agent_menu_drop.add_option('Load Policy from File...', load_policy_from_file, OPEN)
    agent_menu_drop.add_option('Save Policy As...', save_policy_as, SAVE)
    agent_menu_drop.add_option('Load Weights...', load_weights)
    agent_menu_drop.add_option('Save Trained Weights...', save_weights)
    agent_menu_drop.add_separator()
    for (kind, title, _) in PROVIDERS:
        agent_menu_drop.add_option(title, lambda kind=kind: choose_policy(kind))
    agent_menu_drop.add_separator()
    agent_menu_drop.add_option('Evaluate', evaluate, RUN)
    agent_menu_drop.add_option('Step Through...', step_through, STEP)
    agent_menu_drop.add_option('Record', record)
    agent_menu_drop.add_option('Stop', stop_run, STOP)
    agent_menu_drop.add_separator()
    agent_menu_drop.add_option('Run Options...', edit_run_options)

    # view menu
    view_menu = menu.add_cascade("View")
    view_menu_drop = MenuBarMenu(view_menu)
    view_menu_drop.add_option('Toggle Word Wrap', toggle_word_wrap, WRAP)
    view_menu_drop.add_option('Toggle Light/Dark Theme', toggle_theme)

    # buttons: on the right of the menu bar, in groups, and of the header of each pane
    menu.grid_columnconfigure(menu.num, weight=1)
    menu_buttons = (
        (('undo', f'Undo ({UNDO})', undo_text), ('redo', f'Redo ({REDO})', redo_text)),
        (('cut', f'Cut ({CUT})', cut_text), ('copy', f'Copy ({COPY})', copy_text),
         ('paste', f'Paste ({PASTE})', paste_text)),
        (('find', f'Find ({FIND})', find_text),
         ('replace', f'Replace ({REPLACE})', find_and_replace),
         ('goto', f'Go to line ({GOTO})', go_to_line)),
        (('wrap', f'Toggle word wrap ({WRAP})', toggle_word_wrap),
         ('moon', 'Toggle light/dark theme', toggle_theme)),
    )
    column = menu.num + 1
    for (g, group) in enumerate(menu_buttons):
        for (k, (icon, tooltip, command)) in enumerate(group):
            button = IconButton(menu, icon, tooltip, command,
                                dark_name='sun' if icon == 'moon' else None)
            last = k == len(group) - 1
            button.grid(row=0, column=column, pady=2, padx=(
                0, (6 if g == len(menu_buttons) - 1 else 10) if last else 2))
            column += 1
            if icon == 'wrap':
                wrap_button = button

    for (header, noun, commands) in (
            (domain_pane.header, 'domain',
             (create_domain, open_domain, save_domain, save_domain_as)),
            (inst_pane.header, 'instance',
             (create_instance, open_instance, save_instance, save_instance_as))):
        for (icon, tooltip, command) in zip(
                ('new', 'load', 'save', 'save_as'),
                (f'New {noun} ({NEW})', f'Load {noun} from file ({OPEN})',
                 f'Save {noun} ({SAVE})', f'Save {noun} as ({SAVE_AS})'), commands):
            header.add_button(icon, tooltip, command)
            if header is domain_pane.header and icon == 'load':
                header.add_button(
                    'repository', 'Load domain and instance from rddlrepository',
                    open_from_dialog)
    domain_pane.header.add_gap()
    domain_pane.header.add_button(
        'check', f'Check domain and instance ({CHECK})', check_problem)
    domain_pane.header.add_button('graph', 'Show dependency graph', show_dependencies)

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
        policy_header.add_button('run', f'Evaluate ({RUN})', evaluate),
        policy_header.add_button('step', f'Step through ({STEP})', step_through),
        policy_header.add_button('record', 'Record', record, colors=RECORD_COLOR)
    ]
    stop_button = policy_header.add_button('stop', f'Stop ({STOP})', stop_run)
    policy_header.add_gap()
    policy_header.add_button('options', 'Run options', edit_run_options)

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
