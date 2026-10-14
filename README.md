# Dreamscale documentation

User-facing documentation for [Dreamscale](https://app.dreamscalelabs.com),
hosted by Mintlify at
[docs.dreamscalelabs.com](https://docs.dreamscalelabs.com).

The documentation is organized around user jobs:

- try a cloud model in simulation (Quick start);
- set up and run an SO-101 or a bimanual YAM;
- call a model from your own Python code;
- deploy your own fine-tune;
- record runs on HUD or Inspect Robots;
- look up CLI and SDK details, and fix problems.

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

`check_sdk_contract.py` expects the Dreamscale version configured in
`docs.json` to be installed in the active Python environment.

## Publishing

Mintlify deploys the default branch of `Dreamscale-Labs/docs`. Review the
preview deployment before merging. After the docs commit is merged, update the
`mvp/user-docs` submodule pointer in the parent MVP repository as a separate
change.
