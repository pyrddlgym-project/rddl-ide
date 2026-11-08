'''Takes screenshots of the IDE on the display it runs on, to see how it renders on that
platform (on CI: Linux, on a virtual display): in both themes, the main window with an
error marked, an open menu, the JaxPlan form and an open chooser.

    python .github/screenshots.py <output folder>'''
import os
import platform
import subprocess
import sys
import time
import warnings

from customtkinter import CTkFont, set_appearance_mode

from rddl_ide.core.codearea import monospace_family
from rddl_ide.core.popup import ChoiceMenu, MenuBarMenu
from rddl_ide.core.statusbar import StatusBar
from rddl_ide.run import create_window

SAMPLE_DOMAIN = '''domain sample {
    pvariables {
        GAIN : { non-fluent, real, default = 1.0 };
        level : { state-fluent, real, default = 0.0 };
        add : { action-fluent, bool, default = false };
    };
    cpfs {
        level' = if (add) then level + GAIN else level;
    };
    reward = level;
}
'''
SAMPLE_INSTANCE = '''non-fluents sample_nf {
    domain = sample;
}
instance sample_inst {
    domain = sample;
    non-fluents = sample_nf;
    max-nondef-actions = 1;
    horizon = 10;
    discount = 1.0;
}
'''


def sources():
    try:
        from rddlrepository.core.manager import RDDLRepoManager
        info = RDDLRepoManager().get_problem('Wildfire_MDP_ippc2014')
        with open(info.get_domain()) as domain, open(info.get_instance('1')) as instance:
            return domain.read(), instance.read()
    except Exception:
        return SAMPLE_DOMAIN, SAMPLE_INSTANCE


def pump(window, seconds):
    end = time.time() + seconds
    while time.time() < end:
        window.update()
        time.sleep(0.02)


def capture(window, path):
    '''Captures the whole screen, so that popups (separate windows) are included.'''
    pump(window, 0.8)
    try:
        from PIL import ImageGrab
        ImageGrab.grab().save(path)
    except Exception:  # Pillow without X11 support
        subprocess.run(['import', '-window', 'root', path], check=True)
    print('saved', path)


def describe(window, domain, path):
    '''Writes where the screenshots were taken: the platform, Tk, the screen and the
    fonts the IDE actually uses there.'''
    from tkinter import font
    editor_font = font.Font(font=domain.editor.text._textbox.cget('font'))
    lines = [f'platform: {platform.platform()}',
             f'python: {sys.version.split()[0]}, Tk: {window.tk.call("info", "patchlevel")}',
             f'screen: {window.winfo_screenwidth()}x{window.winfo_screenheight()}, '
             f'scaling: {window._get_window_scaling()}',
             f'editor font: {editor_font.actual("family")} {editor_font.actual("size")}',
             f'monospace font chosen: {monospace_family()}',
             f'UI font: {font.Font(font=CTkFont()).actual("family")}']
    with open(path, 'w') as file:
        file.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    if os.environ.get('GITHUB_ACTIONS'):  # also on the run's page, readable without signing in
        print('::notice title=Where the screenshots were taken::' + '%0A'.join(lines))


def main(folder):
    warnings.filterwarnings('ignore')
    os.makedirs(folder, exist_ok=True)
    (domain_text, instance_text) = sources()
    set_appearance_mode('light')
    (window, domain, instance, policy) = create_window()
    window.geometry('1600x950+0+0')
    pump(window, 1.0)
    for (pane, text) in ((domain, domain_text), (instance, instance_text)):
        pane.editor.text.set_text(text)
    lines = domain_text.splitlines()
    line = next((i for (i, text) in enumerate(lines, 1) if "'" in text and '=' in text), 1)
    domain.editor.text.show_error(f'{line}.0', f'{line}.end')
    status = next(w for w in window.winfo_children() if isinstance(w, StatusBar))
    status.show('Step 12/40 · reward 0 · return -130   |   Training 100% · iter 180 · '
                '3.0 s · train -3457.7 · test -1491.2 · best -917.09')
    agent = next(menu for menu in MenuBarMenu._menus if menu.button.cget('text') == 'Agent')
    describe(window, domain, os.path.join(folder, 'info.txt'))

    for theme in ('light', 'dark'):
        set_appearance_mode(theme)
        policy.show_form('builtin')
        capture(window, os.path.join(folder, f'{theme}-1-window.png'))

        agent.open()
        capture(window, os.path.join(folder, f'{theme}-2-menu.png'))
        agent.popup.close()

        policy.show_form('jaxplan-offline')  # shows why, if JaxPlan is not installed
        capture(window, os.path.join(folder, f'{theme}-3-form.png'))

        choosers = list(_widgets(policy, ChoiceMenu))
        if choosers:  # the optimizer's chooser if the form has one, else the first
            chooser = next((c for c in choosers if c.get() in ('rmsprop', 'adam')), choosers[0])
            chooser._open_dropdown_menu()
            capture(window, os.path.join(folder, f'{theme}-4-chooser.png'))
            chooser.popup.close()
    window.destroy()


def _widgets(root, kind):
    for child in root.winfo_children():
        if isinstance(child, kind):
            yield child
        yield from _widgets(child, kind)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'screenshots')
