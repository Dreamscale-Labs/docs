# Dropbear documentation guide

## Project context

- This is the user-facing Dropbear documentation site, built with Mintlify.
- Pages are MDX with YAML frontmatter.
- Navigation, global variables, branding, redirects, and agent instructions
  live in `docs.json`.
- The Python SDK and CLI are the supported public integration surfaces.
- Product behavior must be verified against the published `dropbear` package
  and current production model catalog before it is documented.

## Canonical terminology

- Use **Dropbear**, **Python SDK**, **CLI**, **API key**, **session**, **model**,
  **SO-101**, **Franka**, **MolmoAct2-DROID**, and **LIBERO**.
- Use `molmoact2-so101`, `molmoact2-droid`, and `molmoact2-libero` for exact
  model identifiers.
- Say **action chunk** for the actions returned by `predict()`.
- Distinguish model coordinates from robot-controller coordinates.
- Treat `connect_so101()` as deprecated. Use `dropbear.connect()` in new
  examples.

## Writing standard

- Start with the user outcome and prerequisites.
- Use active voice, second person, and sentence-case headings.
- Keep one main job per page and one idea per sentence.
- Prefer tested, copyable commands and complete Python examples.
- State the expected result after every major procedure.
- End procedures with the next useful action and a recovery link.
- Use tables only for exact mappings or comparisons.
- Use diagrams only when they clarify ownership, ordering, or data flow.
- Keep details progressively disclosed. Recommend automatic defaults before
  advanced overrides.
- Design for humans first, while keeping headings, code, and terms easy for
  coding agents to retrieve.

## Safety rules

- The Python quickstart must not actuate a robot.
- Any motion example must require robot-side position, velocity, acceleration,
  workspace, collision, watchdog, and e-stop protections appropriate to the
  hardware.
- SO-101 motion must follow setup, calibration, diagnostics, dry-run success,
  and explicit operator confirmation.
- Franka examples stop at inference unless the user supplies and validates
  their own controller.
- Never imply that cloud inference replaces a local safety controller.

## Content boundaries

Do not document:

- raw control-plane REST or WebSocket endpoints;
- internal worker, admin, billing-reconciliation, or infrastructure workflows;
- secrets, test credentials, internal tokens, or private operational URLs;
- models marked coming soon or beta-only as generally available;
- exact model prices outside the live dashboard;
- BimanualYAM until it is generally available.

## Page requirements

Every navigable MDX page must include:

- `title`, `description`, and `keywords` frontmatter;
- prerequisites before procedural steps;
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
python3 scripts/check_sdk_contract.py
```
