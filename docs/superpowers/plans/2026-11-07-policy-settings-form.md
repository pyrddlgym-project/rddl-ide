# Policy Settings Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the code-based baseline policies in the policy pane with forms that list every setting of the installed packages (JaxPlan, Gurobi, pyRDDLGym agents, Stable-Baselines3), extracted by introspection.

**Architecture:** A UI-free `rddl_ide.core.settings` package describes each baseline as a *provider*: a list of sections (each optionally with a class chooser) whose fields are read from signatures at run time, plus functions that turn a form state into a config string / policy and back. A customtkinter `SettingsForm` widget renders any provider; the policy pane switches between that form and the code editor (custom policies).

**Tech Stack:** Python ≥ 3.11, `inspect` + `ast` for extraction, `configparser` + `ast.literal_eval` for configs, customtkinter 5/6 + CTkMenuBar, `unittest` (no pytest available).

**Spec:** `docs/superpowers/specs/2026-11-07-policy-settings-form-design.md`

## Global Constraints

- No hand-maintained lists of package settings; only the per-provider "not configurable" exclusion lists.
- Every setting stays editable: anything without a typed field is reachable through a section's "additional settings" dict field.
- Configs written for JaxPlan/Gurobi load with the package's own `load_config`; only changed settings are written; first line `# rddl-ide: <kind>`.
- Extraction needs no Gurobi license and no GPU; a missing package shows a message, never a crash.
- Do not install packages into the user's environments; tests run with `jaxenv` / `gurobienv` (+ `PYTHONPATH` to checkouts) and skip what is missing.
- TODO comment where untraceable `*_kwargs` fall back to a dict field: "add trace hints to pyRDDLGym-jax".

## Review Focus

1. A value typed without quotes for a string setting (`cvar`, `adam`) — expected: taken as a string.
2. `inf` / `-inf` (Gurobi `TimeLimit` default) — expected: parsed as floats, not strings.
3. A traced nested table with one sub-value set but a required sub-value (`eta`) empty — expected: a clear error naming `noise_kwargs.eta`, run not started.
4. Loading a `.cfg` with keys the form does not know (`stopping_rule_kwargs`) — expected: kept in the section's additional settings and written back on save.
5. Switching planner Backprop → PGPE → Backprop — expected: Backprop edits restored, auxiliary back to Backprop's default.

---

### Task 1: Introspection primitives

**Files:**
- Create: `rddl_ide/core/settings/__init__.py`, `rddl_ide/core/settings/introspect.py`, `rddl_ide/core/settings/model.py`
- Test: `tests/test_introspect.py`, `tests/test_model.py`

**Interfaces — Produces:**
- `introspect.MISSING` sentinel; `signature_fields(obj, exclude=frozenset()) -> list[Field]` (classes: MRO union of `__init__` params, first default wins; functions: signature; skips self/*args/**kwargs).
- `introspect.concrete_subclasses(module, base) -> dict[str, type]` (defined in `module`, not abstract, not `base`).
- `introspect.trace_kwargs_target(modules, kwargs_name) -> Callable | None` (ast: `f(**x)`, `f(**self.x)`, `f(**self._x)`; dotted names resolved in the module namespace).
- `model.Field(name, default=MISSING, nested: list[Field] | None = None)`, `.required`.
- `model.format_value(v) -> str` (repr for literals, `__name__` for named callables/classes, `<default>` otherwise; `inf` → `inf`).
- `model.parse_value(text) -> Any` (`literal_eval`; `inf`/`-inf`/`nan` → float; otherwise the text as str).
- `model.Section(id, title, fields: Callable[[str|None], list[Field]], chooser: str|None=None, options: Callable[[FormState], list[str]]=..., default_option: Callable[[FormState], str|None]=..., visible: Callable[[FormState], bool]=...)`.
- `model.FormState` with `choice(section) -> str|None`, `set_choice`, `text(section, option, path) -> str|None`, `set_text`, `extra(section) -> str`, `set_extra`.
- `model.changed_values(state, section, fields) -> dict` (parsed changed values; nested dicts for traced fields; extra dict merged; raises `ValueError("<section>: <path> is required")` for missing required).

- [ ] Tests: `signature_fields(DefaultJaxRDDLCompilerWithGrad)` has ≥ 30 fields incl. `sigmoid_weight`; `trace_kwargs_target([planner, plan], 'noise_kwargs') is optax.add_noise`; `parse_value('cvar') == 'cvar'`, `parse_value('inf') == float('inf')`, `parse_value('[1, 2]') == [1, 2]`; `format_value(jnp.tanh) == 'tanh'`; `changed_values` raises for empty required nested `eta` once `gamma` is set.
- [ ] Run `python -m unittest tests.test_introspect tests.test_model` → FAIL, implement, → PASS.

### Task 2: JaxPlan provider

**Files:** Create `rddl_ide/core/settings/jaxplan.py`; Test `tests/test_jaxplan.py`

**Interfaces — Consumes:** Task 1. **Produces:** `JaxPlanProvider(online: bool)` with `kind` (`'jaxplan-offline'|'jaxplan-online'`), `title`, `sections() -> list[Section]`, `initial_state() -> FormState` (from the package's `examples/configs/default_slp.cfg` / `default_replan.cfg` if present), `env_args(state) -> dict` (`{'vectorized': True}`), `to_config(state) -> str`, `from_config(text) -> FormState`, `build_policy(env, state)`.

Sections: compiler (chooser over `logic` classes named `*Compiler*`), planner (chooser over `JaxPlanner` subclasses; fields exclude `auxiliary`, `optimizer`, `optimizer_kwargs`), auxiliary (options `None` + planners; default = class of the planner's default `auxiliary` instance or `None`; fields = class fields minus `JaxPlanner.__init__` params), plan (`method`, `JaxPlan` subclasses → `method_kwargs`), optimizer (visible iff planner has `optimizer`; options = public optax functions with `learning_rate` returning `GradientTransformation`; default = planner default's `__name__`; fields → `optimizer_kwargs`, only if planner has `optimizer_kwargs`), optimize (`optimize_generator` + chosen controller's own params). `build_policy` mirrors `examples/run_plan.py` (`load_config_from_string` → `create_planner(rddl=env.model, dashboard_viz=env._visualizer, ...)` → controller; launch dashboard if present).

- [ ] Tests: for every planner × plan, `to_config(fresh state)` loads with `load_config_from_string`; LMMAES and PGPE field sets differ; Backprop default auxiliary is `JaxLMMAESPlanner`; edited aux field writes both `auxiliary=` and `auxiliary_kwargs=`; round trip `to_config(from_config(c)) == c` for the package's `default_*.cfg` files; unknown `stopping_rule_kwargs` survives round trip; a short offline SLP run on `Reservoir_Continuous` instance 1 finishes.
- [ ] Run `python -m unittest tests.test_jaxplan` (jaxenv) → FAIL, implement, → PASS.

### Task 3: Built-in agents and Gurobi providers

**Files:** Create `rddl_ide/core/settings/builtin.py`, `rddl_ide/core/settings/gurobi.py`; Test `tests/test_builtin.py`, `tests/test_gurobi.py`

**Produces:** `BuiltinAgentProvider` (`kind='builtin'`; chooser over concrete `BaseAgent` subclasses of `pyRDDLGym.core.policy`, default `NoOpAgent`; IDE supplies `env` / `action_space`; IDE INI config `[Agent] agent=...`). `GurobiProvider` (`kind='gurobi-online'`; `[Optimizer]` chooser over `GurobiPlan` subclasses → `method`/`method_kwargs`, fields from `GurobiRDDLCompiler.__init__` minus `rddl, plan, logger`; `[Gurobi]` fields from `GRB.Param` with defaults from `gp.Env(empty=True).getParam`; initial state from `examples/default.cfg`; `build_policy` = `GurobiOnlineController(rddl=env.model, **load_config_from_string(cfg))`).

- [ ] Tests: RolloutAgent `num_candidates` is required and an unfilled run raises; Random agent runs one Wildfire episode; Gurobi has ≥ 200 solver params, `TimeLimit` default `inf`, round trip of `examples/default.cfg`; Gurobi online runs one episode of a small domain (skipped without gurobipy).
- [ ] Run (jaxenv for builtin; gurobienv with `PYTHONPATH=<pyRDDLGym-gurobi checkout>` for gurobi) → FAIL, implement, → PASS.

### Task 4: Stable-Baselines3 provider (untested until the user's RL env exists)

**Files:** Create `rddl_ide/core/settings/sb3.py`; Test `tests/test_sb3.py` (skipped without stable_baselines3)

**Produces:** `StableBaselinesProvider` (`kind='sb3'`; `[Algorithm]` chooser over `METHODS` keys, fields from the class MRO minus `policy`, `env`; `[Trainer]` `StableBaselinesTrainer` params minus `env`, `method`; `[Train]` `StableBaselinesTrainer.train` minus `callback`; `[Environment]` `SimplifiedActionRDDLEnv` own params; env args `base_class=SimplifiedActionRDDLEnv` + env fields).

- [ ] Test: provider lists `ppo`, PPO has `n_steps`; config round trip. Run → SKIP here.

### Task 5: Settings form widget, policy pane, menus, execution

**Files:**
- Create: `rddl_ide/core/form.py` (`SettingsForm(master, provider, state)` on `CTkScrollableFrame`: sections collapsible, first open; chooser `CTkOptionMenu`; bool fields `CTkCheckBox`, others `CTkEntry`; changed name label in yellow; "show changed only"; nested rows indented; "additional settings" entry per section; redraw all sections on any chooser change), `rddl_ide/core/policypane.py` (`PolicyPane(master)`: header, `show_code(text, caption)`, `show_form(provider, state=None)`, `policy() -> (build_policy, env_args)`, `save(path)`, `load(path)`; providers that fail to import show a message).
- Modify: `rddl_ide/core/execution.py` (split into `policy_from_code(source)` and `evaluate_policy(domain, inst, build_policy, env_args, viz, record)`), `rddl_ide/core/menubar.py` (Baseline menu: Built-in agent, JaxPlan (offline), JaxPlan (online), Gurobi (online), Stable-Baselines3; Load/Save handle `.py` and `.cfg`; start on Built-in agent), `rddl_ide/run.py` (use `PolicyPane`).
- Delete: `rddl_ide/core/prefab/policies/`.

- [ ] Drive the GUI programmatically (scratch script): each menu entry renders; switching planner redraws; editing marks yellow; Save → `.cfg` → Load restores; Evaluate with Built-in Random and JaxPlan offline (short `train_seconds`) runs without errors.
- [ ] Run all unit tests again.
