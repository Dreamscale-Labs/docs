# Dropbear documentation

User-facing documentation for [Dropbear](https://dropbear.dreamscalelabs.com),
hosted by Mintlify at
[docs.dropbear.dreamscalelabs.com](https://docs.dropbear.dreamscalelabs.com).

The documentation is organized around user jobs:

- request a policy prediction from Python;
- integrate Dropbear with an existing robot controller;
- set up and run an SO-101 safely;
- request MolmoAct2-DROID actions for a Franka;
- run the browser simulation;
- diagnose SDK, CLI, network, session, and hardware failures.

The supported public integration surfaces are the Python SDK and CLI. This
repository does not document internal control-plane, worker, infrastructure, or
admin APIs.

## Local development

Install the Mintlify CLI:

```bash
npm install --global mint@4.2.742
```

Start a local preview from this directory:

```bash
mint dev
```

The preview is available at `http://localhost:3000`.

## Validation

Run the same checks used by CI:

```bash
mint validate
mint broken-links --check-anchors --check-redirects --check-snippets
mint a11y
python3 scripts/check_content.py
python3 scripts/check_sdk_contract.py
```

`check_sdk_contract.py` expects the Dropbear version configured in
`docs.json` to be installed in the active Python environment.

## Publishing

Mintlify deploys the default branch of `Dreamscale-Labs/docs`. Review the
preview deployment before merging. After the docs commit is merged, update the
`mvp/user-docs` submodule pointer in the parent MVP repository as a separate
change.
