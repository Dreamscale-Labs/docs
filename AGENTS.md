# Dreamscale documentation guide

## Project context

- This is the user-facing Dreamscale documentation site, built with Mintlify.
- Pages are MDX with YAML frontmatter.
- Navigation, global variables, branding, redirects, and agent instructions
  live in `docs.json`.
- The Python SDK and CLI are the supported public integration surfaces.
- Product behavior must be verified against the published `dreamscale` package
  and current production model catalog before it is documented.

## Canonical terminology

- Use **Dreamscale**, **Python SDK**, **CLI**, **API key**, **session**, **model**,
  **deployment**, **SO-101**, **Bimanual YAM**, and **LIBERO**.
- Use exact model identifiers in code, for example `molmoact2-so101`,
  `molmoact2-bimanual-yam`, `pi0.5-bimanualyam`, and `pi0.5-libero`.
- Say **action chunk** for the actions returned by `predict()`.
- Distinguish model coordinates from robot-controller coordinates.
- Write for a first-time user: no legacy names, migrations, or version
  qualifiers such as "from SDK 0.1.0a…".

## Sidebar

- Group pages by what the reader wants to do, never by interface: Get started
  (Quick start, Models), Run on your robot (one CLI page per supported robot,
  then Python SDK for any other robot), Improve your model (Training,
  Deployments), Help.
- One page per task. Where the CLI and Python both work, show the CLI command
  first, then the Python line.
- Models is the one catalog of which model runs on which robot. A new robot is
  one page under Run on your robot; a new model is one row in Models and one
  line on its robot page.

## Writing standard

- Six main pages (Quick start, SO-101, Bimanual YAM, Python, Models,
  Troubleshooting), about 2,000 words in total, plus short Training and
  Deployments pages. `scripts/check_content.py` enforces the budget.
- Plain Markdown. At most one table per page. The robot safety warning
  (`<Warning>`) is the only callout. No images.
- Document only the shared launch models. The docs are the spec: the SDK and
  CLI match them, and `scripts/run_snippets.py` runs every snippet.
- Keep pages short. Prefer a command or a step list over prose.
- Start with the user outcome and prerequisites.
- Use active voice, second person, and sentence-case headings.
- Keep one main job per page and one idea per sentence.
- Prefer tested, copyable commands and complete Python examples.
- Each step is a command plus how you know it worked.
- End procedures with the next useful action and a recovery link.
- Keep details progressively disclosed. Recommend automatic defaults before
  advanced overrides.
- Design for humans first, while keeping headings, code, and terms easy for
  coding agents to retrieve.

## Safety rules

- The quick start runs in simulation and never moves a robot.
- Any motion example must sit behind a visible warning about local limits and
  a physical e-stop.
- Robot pages follow setup, diagnostics, a no-motion preview, and explicit
  operator confirmation before motion.
- Never imply that cloud inference replaces a local safety controller.

## Content boundaries

Do not document:

- raw control-plane REST or WebSocket endpoints;
- internal worker, admin, billing-reconciliation, or infrastructure workflows;
- secrets, test credentials, internal tokens, or private operational URLs;
- models marked coming soon or beta-only as generally available;
- prices, except the one pricing line on the Quick start page.

## Page requirements

Every navigable MDX page must include:

- `title`, `description`, and `keywords` frontmatter;
- prerequisites ("What you need") before procedural steps;
- language tags on code fences;
- root-relative internal links;
- descriptive alt text for meaningful images;
- a visible safety warning before motion-related code;
- a support path to `team@dreamscalelabs.com` when recovery may require help.

Before publishing, run:

```bash
mint validate
mint broken-links --check-anchors --check-redirects --check-snippets
mint a11y
python3 scripts/check_content.py
python3 scripts/run_snippets.py
```
