import os
from tkinter import END, Menu
import tkinter.filedialog as fd

from core.execution import evaluate_policy_fn

DOMAIN_TEMPLATE = '''
domain Untitled {
        
    types {

    };
            
    pvariables {

    };
        
    cpfs {
    
    };
                
    reward = ;        
}
'''

INSTANCE_TEMPLATE = '''
non-fluents nf_Untitled {

    domain = ;
    
    objects {
        
    };
    
    non-fluents {
        
    };
}

instance Untitled_inst {

    domain = Untitled;

    non-fluents = nf_Untitled;
    
    init-state {
    
    };

    max-nondef-actions = ;
    
    horizon = ;
    
    discount = ;
}
'''


def assign_menubar_functions(domain_window, inst_window, domain_editor, inst_editor):
    domain_file, inst_file = None, None
    
    # FILE functions
    def create_domain():
        global domain_file
        domain_file = None
        domain_window.title('[Domain] Untitled.rddl')
        domain_editor.delete(1.0, END)
        domain_editor.insert(1.0, DOMAIN_TEMPLATE)
        
    def create_instance():
        global inst_file
        inst_file = None
        inst_window.title('[Instance] Untitled.rddl')
        inst_editor.delete(1.0, END)
        inst_editor.insert(1.0, INSTANCE_TEMPLATE)
    
    def open_domain():
        global domain_file        
        domain_file = fd.askopenfilename(defaultextension='.rddl',
                                         filetypes=[('RDDL File', '*.rddl*')])
        if domain_file == '': domain_file = None            
        if domain_file is not None:
            domain_window.title(f'[Domain] {os.path.basename(domain_file)}')
            domain_editor.delete(1.0, END)
            with open(domain_file, 'r') as new_file:
                domain_editor.insert(1.0, new_file.read())
                new_file.close()
    
    def open_instance():
        global inst_file        
        inst_file = fd.askopenfilename(defaultextension='.rddl',
                                       filetypes=[('RDDL File', '*.rddl*')])
        if inst_file == '': inst_file = None            
        if inst_file is not None:
            inst_window.title(f'[Instance] {os.path.basename(inst_file)}')
            inst_editor.delete(1.0, END)
            with open(inst_file, 'r') as new_file:
                inst_editor.insert(1.0, new_file.read())
                new_file.close()
    
    def save_domain():
        global domain_file        
        if domain_file is None:
            domain_file = fd.asksaveasfilename(initialfile='Untitled.rddl',
                                               defaultextension='.rddl',
                                               filetypes=[('RDDL File', '*.rddl*')])
            if domain_file == '': domain_file = None            
        if domain_file is not None: 
            with open(domain_file, 'w') as new_file:
                new_file.write(domain_editor.get(1.0, END))
                new_file.close()
            domain_window.title(f'[Domain] {os.path.basename(domain_file)}')
        
    def save_instance():
        global inst_file        
        if inst_file is None:
            inst_file = fd.asksaveasfilename(initialfile='Untitled.rddl',
                                             defaultextension='.rddl',
                                             filetypes=[('RDDL File', '*.rddl*')])
            if inst_file == '': inst_file = None            
        if inst_file is not None: 
            with open(inst_file, 'w') as new_file:
                new_file.write(inst_editor.get(1.0, END))
                new_file.close()
            inst_window.title(f'[Instance] {os.path.basename(inst_file)}')
    
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
    
    # RUN functions
    def evaluate():
        global domain_file, inst_file
        save_domain()
        save_instance()
        if domain_file is not None and inst_file is not None:
            policy_file = fd.askopenfilename(defaultextension='.py',
                                             filetypes=[('Python File', '*.py*')])
            evaluate_policy_fn(domain_file, inst_file, policy_file)
            
    # create menu bars
    domain_menu = Menu(domain_window)
    inst_menu = Menu(inst_window)
    
    # domain file menu
    domain_file_menu = Menu(domain_menu, tearoff=False, activebackground='DodgerBlue')
    domain_file_menu.add_command(label='New Domain', command=create_domain)
    domain_file_menu.add_command(label='Open Domain...', command=open_domain)
    domain_file_menu.add_command(label='Save Domain', command=save_domain)
    domain_file_menu.add_command(label='Save Domain As...', command=save_domain_as)
    domain_file_menu.add_separator()
    domain_file_menu.add_command(label='Exit', command=exit_application)
    domain_menu.add_cascade(label='File', menu=domain_file_menu)
    
    # instance file menu
    inst_file_menu = Menu(inst_menu, tearoff=False, activebackground='DodgerBlue')
    inst_file_menu.add_command(label='New Instance', command=create_instance)
    inst_file_menu.add_command(label='Open Instance...', command=open_instance)
    inst_file_menu.add_command(label='Save Instance', command=save_instance)
    inst_file_menu.add_command(label='Save Instance As...', command=save_instance_as)
    inst_menu.add_cascade(label='File', menu=inst_file_menu)
    
    # domain edit menu
    domain_edit_menu = Menu(domain_menu, tearoff=False, activebackground='DodgerBlue')
    domain_edit_menu.add_command(label='Copy', command=copy_domain_text)
    domain_edit_menu.add_command(label='Cut', command=cut_domain_text)
    domain_edit_menu.add_command(label='Paste', command=paste_domain_text)
    domain_menu.add_cascade(label='Edit', menu=domain_edit_menu)
    
    # instance edit menu
    inst_edit_menu = Menu(inst_menu, tearoff=False, activebackground='DodgerBlue')
    inst_edit_menu.add_command(label='Copy', command=copy_instance_text)
    inst_edit_menu.add_command(label='Cut', command=cut_instance_text)
    inst_edit_menu.add_command(label='Paste', command=paste_instance_text)
    inst_menu.add_cascade(label='Edit', menu=inst_edit_menu)
    
    # run menu
    run_menu = Menu(domain_menu, tearoff=False, activebackground='DodgerBlue')
    run_menu.add_command(label='Evaluate', command=evaluate)
    domain_menu.add_cascade(label='Run', menu=run_menu)
    
    # assign menu bar to window
    domain_window.config(menu=domain_menu)
    inst_window.config(menu=inst_menu)
    
    return domain_menu, inst_menu
