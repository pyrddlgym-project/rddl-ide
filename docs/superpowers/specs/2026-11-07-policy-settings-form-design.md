# Policy settings form — design

Date: 2026-11-07
Status: draft for review

## Intent

The policy pane of RDDL-IDE currently shows Python source for each baseline policy, with
planner settings written inside a config string (for JaxPlan, a `PARAMETERS = """..."""`
block). Someone who did not write JaxPlan cannot tell which settings exist: the config
only lists values that deviate from defaults or that are "typically" changed, and the
remaining ~100 settings of a JaxPlan run are invisible unless you read the source.

The point of a GUI is not having to write code. Built-in baselines should be configured
through a form that lists **every** setting the installed package accepts, with its
default value, and redraws when the user picks a different class (planner, plan,
algorithm, agent). The list of settings must be extracted from the installed packages at
run time, not hard-coded, because the packages change between versions.

## Goals

- For each built-in baseline, show a form listing every constructor/config setting the
  installed package accepts, prefilled with its default.
- Class choices (planner, plan/policy, optimizer, auxiliary planner, agent type, RL
  algorithm) are dropdowns whose options are discovered from the installed package; picking
  one redraws the settings below it from that class's signature.
- Settings whose value is a `*_kwargs` dict get a nested table when the target function can
  be traced from the package source; otherwise they are a plain dict field the user fills in.
- Running a form-based baseline builds the policy from the form values; no Python is shown.
- Saving a form-based policy saves its config; loading a config fills the form back in.
- Custom Python policies remain possible ("Load Policy from File"), shown in a code editor.

## Non-goals (for now)

- Descriptions/tooltips for settings. Docstrings exist for many settings, but showing them
  is deferred; showing every setting with its default is the accomplishment.
- Trace hints in pyRDDLGym-jax (or other packages) for settings that cannot be traced
  automatically. **TODO (recorded):** add trace hints to pyRDDLGym-jax later, so that
  `utility_kwargs`, `time_embedding_kwargs`, `reduce_on_plateau_kwargs`,
  `optimizer_kwargs_mu`/`optimizer_kwargs_sigma` and the like can get nested tables. Until
  then these are dict fields. Also leave a `TODO` comment at the place in the code where the
  untraceable fallback is chosen.
- `optax.contrib` optimizers.
- RLlib, and offline Gurobi.
- Validation beyond what the packages' own loaders/constructors do at run time.

## Anti-goals

- A hand-maintained list of each package's settings. If a new JaxPlan version adds a
  planner argument, the form must show it without an IDE change.
- A form that silently drops settings it does not understand. Anything that cannot be
  presented as a typed field must still be editable (as a literal/dict field), never hidden,
  except for the small set of arguments a config cannot set at all (below).

## User-facing behaviour

### Baseline menu

The Baseline menu offers these entries; each one switches the policy pane to a form:

| Menu entry | Dropdown at the top of the form | Built from |
|---|---|---|
| Built-in agent | agent: No-op, Random, Rollout, Random Shooting | pyRDDLGym `core.policy` agents |
| JaxPlan (offline) | (form described below) | `JaxOfflineController` |
| JaxPlan (online) | (form described below) | `JaxOnlineController` |
| Gurobi (online) | plan class | `GurobiOnlineController` |
| Stable-Baselines3 | algorithm, from `pyRDDLGym_rl.core.sb3_trainer.METHODS` | `StableBaselinesTrainer` |

The SLP / DRP / replan prefab files are replaced: SLP vs DRP is the JaxPlan `method`
setting; offline vs online is the menu entry.

"Load Policy from File..." switches the pane to the code editor for a custom Python policy
(current behaviour, same `build_policy(env)` / `required_env_args()` contract). Custom
policies are rare but must keep working.

### The form

- Grouped into collapsible sections (for JaxPlan: Compiler, Planner, Auxiliary planner,
  Plan/policy, Optimizer, Optimize, Controller).
- Each setting is a row: name, value field prefilled with the default.
- A row whose value differs from its default is highlighted.
- A "show changed only" toggle hides unchanged rows.
- Class dropdowns redraw the rows that depend on them. Edits to a class's rows are kept per
  class for the session (switching away and back restores them).
- Picking a different Baseline menu entry resets the form.
- Required arguments with no default (e.g. `RolloutAgent.num_candidates`,
  `optax.add_noise.eta`) are shown empty and flagged; running with one unfilled reports an
  error instead of starting.

The interactive mockup produced while designing (built from the installed JaxPlan by
introspection) is the reference for look and behaviour: sections, class dropdowns that
redraw, yellow changed rows, show-changed-only.

### Save / load

- "Save Policy As..." on a form policy saves its config; on a custom policy it saves the
  `.py` file (as today).
- JaxPlan and Gurobi configs are saved in each package's own `.cfg` format, so the file can
  be used with `load_config(...)` outside the IDE. Only settings that differ from their
  defaults are written, matching how hand-written configs look today.
- Built-in agent and Stable-Baselines3 have no package config format; the IDE saves them in
  the same INI style (section per group, values as Python literals).
- "Load Policy from File..." accepts a `.cfg` as well as a `.py`: a config opens in the
  matching form with its values filled in.

## How settings are extracted

General rule: a group of settings is the parameter list of a callable, read with
`inspect.signature`. For a class, walk its MRO and union the `__init__` parameters of every
class that defines one (first definition wins for the default), skipping `self`, `*args`
and `**kwargs`. This is what makes `DefaultJaxRDDLCompilerWithGrad` (whose own `__init__`
takes nothing) show its 33 inherited settings, and the planners show the `JaxPlanner`
arguments they forward through `**planner_kwargs`.

Arguments a config cannot set (objects the loader or runtime supplies) are excluded by a
short list kept in the IDE: for JaxPlan `rddl`, `plan`, `compiler`, `compiler_kwargs`,
`logger`, `dashboard_viz`, `python_functions`, `critic`, and for `optimize`: `key`, `subs`,
`guess`, `model_params`, `critic_params`, `dashboard_id`, `tqdm_position`. This list is the
one piece of package knowledge the IDE maintains by hand.

### JaxPlan (pyRDDLGym-jax)

| Section | Source |
|---|---|
| `[Compiler] method` dropdown | classes in `pyRDDLGym_jax.core.logic` that are complete compilers (default `DefaultJaxRDDLCompilerWithGrad`); rows from the chosen class's MRO |
| `[Planner] planner` dropdown | non-abstract subclasses of `JaxPlanner` in `pyRDDLGym_jax.core.planner` (today: Backprop, PGPE, LMMAES; default Backprop) |
| `[Planner]` rows | chosen planner's MRO, minus the class-choice settings below |
| `[Planner] method` dropdown | subclasses of `JaxPlan` in `pyRDDLGym_jax.core.plan` (SLP, DRP, ...); rows go to `method_kwargs` |
| `[Planner] optimizer` dropdown | every public optax function that takes `learning_rate` and returns a `GradientTransformation` (30 in optax 0.2.8); rows go to `optimizer_kwargs`. Shown only if the chosen planner has an `optimizer` argument. This is the one deliberate exception to "untraceable `*_kwargs` are dict fields". |
| `[Planner] auxiliary` dropdown | `None` plus the planner classes; rows are only the arguments the chosen class adds on top of `JaxPlanner.__init__` (an auxiliary planner ignores the shared ones); rows go to `auxiliary_kwargs` |
| `[Optimize]` rows | `JaxPlanner.optimize_generator` (`optimize` itself only takes `*args, **kwargs`), plus the chosen controller's own arguments |

Defaults that are objects rather than literals need care:
- Backprop's default `auxiliary` is a `JaxLMMAESPlanner()` instance: show it as the
  dropdown value `JaxLMMAESPlanner` with that class's defaults. Choosing `None` writes
  `auxiliary=None`. Because `config.py` rejects `auxiliary_kwargs` without `auxiliary`, any
  edited auxiliary row also writes `auxiliary='<class>'`.
- Function-valued defaults (e.g. DRP `activation=jnp.tanh`) are shown by name; the config
  loader resolves names (`'tanh'`) itself.

### `*_kwargs` nested tables

A setting whose name contains `kwargs` gets a nested table only if its target can be traced:
parse the package source with `ast`, find calls `f(**name)` / `f(**self.name)` /
`f(**self._name)`, and resolve `f` as a dotted name in that module's namespace. Today that
traces `noise_kwargs` → `optax.add_noise`, `line_search_kwargs` →
`optax.scale_by_zoom_linesearch`, `normalizer_kwargs` → `LayerNorm`. Every other `*_kwargs`
is a dict field (see the TODO above).

### Gurobi (pyRDDLGym-gurobi)

- `[Optimizer] method` dropdown: subclasses of `GurobiPlan` (straight-line, piecewise,
  quadratic); rows go to `method_kwargs`.
- `[Optimizer]` rows: `GurobiRDDLCompiler.__init__` minus `rddl`, `plan`, `logger`
  (`rollout_horizon`, `epsilon`, `float_range`, `piecewise_options`,
  `allow_synchronous_state`, `verbose`, ...).
- `[Gurobi]` rows: all solver parameters, listed from `gurobipy.GRB.Param` with defaults
  read from an unstarted environment, `gp.Env(empty=True).getParam(name)`. This needs no
  license (verified: 207 parameters with gurobipy 13.0.3). Saved as the `[Gurobi]` section,
  which the loader passes as `model_params`.

### Built-in agents (pyRDDLGym)

Agent dropdown: `NoOpAgent`, `RandomAgent`, `RolloutAgent`, `RandomShootingAgent`, found as
the concrete `BaseAgent` subclasses in `pyRDDLGym.core.policy`. Rows from the chosen class's
signature, with `env` / `action_space` supplied by the IDE.

### Stable-Baselines3 (pyRDDLGym-rl)

- Algorithm dropdown: keys of `pyRDDLGym_rl.core.sb3_trainer.METHODS` (built from whatever
  stable-baselines3 and sb3-contrib provide).
- Algorithm rows: the chosen algorithm's `__init__` (MRO), minus `policy` and `env`;
  `policy_kwargs` is a dict field.
- Trainer rows: `StableBaselinesTrainer` `policy`, `progress`, `progress_kwargs`;
  training length `total_timesteps` from `train(...)`.
- Env rows: `SimplifiedActionRDDLEnv` own arguments (`action_mode`, `num_bins`,
  `normalize_actions`, `print_summary`).

## Running a form policy

- JaxPlan and Gurobi: generate the package's config string from the form (changed values
  only), then go through the package's own path: `load_config_from_string` → planner →
  controller. This keeps the IDE's behaviour identical to a saved `.cfg` run.
- Built-in agents and Stable-Baselines3: call the constructors with the changed values as
  keyword arguments.
- Environment arguments each baseline needs are supplied by the IDE (JaxPlan:
  `vectorized=True`; SB3: `base_class=SimplifiedActionRDDLEnv` plus the env rows).
- Errors from the package (bad value, unknown class, missing required argument) are shown
  in the existing error dialog.

## Constraints

- Must work with whatever versions are installed; a baseline whose package is not
  installed is still listed but shows a message instead of a form when chosen.
- GUI stack stays customtkinter + CTkMenuBar inside the existing single window.
- Python ≥ 3.11 (current `requires-python`). Tk 9 (Python 3.14) must work.
- Extraction must not need a Gurobi license or a GPU.

## Calls made during design review (not discussed with the user; check these)

- **Value entry:** each field is parsed with `ast.literal_eval`, like the packages' config
  loaders. If parsing fails and the default is a string, the text is taken as a string, so
  `utility` can be typed as `cvar` or `'cvar'`. Bool defaults get a checkbox.
- **Defaults that are not literals and have no useful name** (e.g. DRP `initializer`,
  whose default is an anonymous closure shown as `init`) display as `<default>` and are never
  written to the config unless the user replaces them.
- **Which form a saved config belongs to:** the IDE writes a first-line comment such as
  `# rddl-ide: jaxplan-online`. configparser ignores comments, so the file still loads with
  the package's own `load_config`. A `.cfg` without that line is matched by its sections
  (`[Compiler]`/`[Planner]`/`[Optimize]` → JaxPlan offline; `[Gurobi]`/`[Optimizer]` →
  Gurobi). A saved JaxPlan config could not otherwise say whether it is offline or online.
- **Prefab policy files:** `jax_slp.py`, `jax_drp.py`, `jax_replan.py`,
  `gurobi_replan.py`, `sb3_ppo.py`, `noop.py`, `random.py` are removed once the forms
  replace them.
- **Many rows:** sections other than the first are collapsed by default and only built when
  opened, so a ~100-row JaxPlan form stays responsive in customtkinter.

## Builder's calls (left to the implementer)

- Exact widgets (e.g. checkbox for bool defaults, text field parsed with
  `ast.literal_eval` otherwise), layout details, and scrolling in a narrow pane.
- Module structure (e.g. one introspection module per package behind a common
  "settings provider" shape).
- How compiler classes in `logic` are told apart from mixins for the compiler dropdown.
- Caching of extracted settings per session.

## Testing

- Extraction is tested headless against the installed packages: every JaxPlan planner,
  plan, optimizer and auxiliary combination yields a settings list, and a form with no edits
  produces a config that the package's own loader accepts and runs.
- Round-trip: config → form → config gives back the same settings.
- GUI behaviour (redraw on class change, highlight, save/load) is driven programmatically
  as in the existing GUI tests.
- Environments: `jaxenv` (pyRDDLGym-jax editable), `gurobienv` (gurobipy 13.0.3, free
  pip license; the expired `~/gurobi.lic` was renamed to `gurobi.lic.expired` so that the
  bundled license is used).
