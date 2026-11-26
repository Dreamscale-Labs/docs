# Dreamscale documentation guide

User-facing docs for the Python SDK and CLI, the only public integration
surfaces, built with Mintlify: MDX pages, with navigation, variables, and
redirects in `docs.json`. Merging to `main` publishes to docs.dreamscalelabs.com.

## The docs are the spec

- Document only behavior verified against the published `dreamscale` package
  (`sdkVersion` in `docs.json`) and the current production model catalog.
- Document only the shared launch models. `DOCUMENTED_MODELS` and `BASE_MODELS`
  in `scripts/check_content.py` are that list: add an id there in the same change
  that documents it, and name beta models as beta on their page.
- Model ids are irregular (`pi0.5-bimanualyam`, `molmoact2-bimanual-yam`,
  `pi0.5-libero`): copy them exactly, never normalise them.
- Write for a first-time user: no legacy names, migrations, or version
  qualifiers such as "from SDK 0.1.0a…".
- Say **action chunk** for what `predict()` returns, and keep model coordinates
  distinct from robot-controller coordinates.

## Structure

- The sidebar groups pages by what the reader wants to do, never by interface:
  Get started, Run on your robot (one CLI page per robot, then Python for any
  other robot), Improve your model, References, Help.
- Models is the one catalog of which model runs on which robot. A new robot is
  one page under Run on your robot; a new model is one row in Models and one
  line on its robot page.
- One page per task. Where the CLI and Python both work, show the CLI command
  first, then the Python line.
- The CLI and SDK references list every public command, option, function, and
  parameter, and nothing else: hidden CLI commands and options, and SDK names the
  guides don't use (the raw session API, unreleased robots' helpers), stay out.
- Each step is a command plus how you know it worked. Where recovery may need
  help, give the support path to `team@dreamscalelabs.com`.

## Safety

- The quick start runs in simulation and never moves a robot.
- Robot pages go setup, diagnostics, a visible `<Warning>` about local limits and
  a physical e-stop, then a run that previews and waits for the operator's
  confirmation before motion.
- Never imply that cloud inference replaces a local safety controller.

## Never document

- raw control-plane REST or WebSocket endpoints;
- internal worker, admin, billing-reconciliation, or infrastructure workflows;
- secrets, test credentials, internal tokens, or private operational URLs;
- models marked coming soon or beta-only as generally available;
- prices, except the one pricing line on the Quick start page.

## Validation

CI (`.github/workflows/validate.yml`) runs the five commands in `README.md`
§ Validation; run them locally with `dreamscale==<sdkVersion>` installed.
`scripts/check_content.py` enforces frontmatter, the one-callout, one-table, and
no-image rules, the launch-model list, and the main-page word budget.
`scripts/run_snippets.py` checks every `dreamscale` command against `--help` and
runs every Python block, except one titled with an SDK name
(```` ```python dreamscale.connect ````), which is a stub `def` checked as that
function's signature.
