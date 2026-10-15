# Dreamscale documentation

User-facing documentation for [Dreamscale](https://app.dreamscalelabs.com),
hosted by Mintlify at
[docs.dreamscalelabs.com](https://docs.dreamscalelabs.com).

The documentation is organized around user jobs, one page each:

- see a model work in two minutes (Quick start);
- run a model on an SO-101 or a bimanual YAM;
- call a model from your own Python code;
- know what each model takes in and returns (Models);
- fix what just failed (Troubleshooting).

A short Deployments page, outside the main path, covers serving your own
fine-tune. It has `hidden: true` until Deployments launch: reachable by URL, but
out of the sidebar, search and indexing. Delete that line to launch it.

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
python3 scripts/run_snippets.py
```

`run_snippets.py` expects the Dreamscale version configured in `docs.json` to
be installed in the active Python environment. It checks every `dreamscale`
command against the CLI's `--help`, runs every Python block against the SDK with
synthetic observations and a stand-in `connect`, and checks the Models table
against the SDK's model contracts.

Before publishing, run the snippets live, one session at a time, first on dev
and then on prod:

```bash
set -a; . ~/.config/dreamscale/dev.env; set +a
python3 scripts/run_snippets.py --live dev --sim --uv
```

Robot commands (`robots`, `run`, `doctor so101|yam`) need hardware, so the
script checks them against `--help` only.

## Publishing

Mintlify deploys the default branch of `Dreamscale-Labs/docs`. Review the
preview deployment before merging. After the docs commit is merged, update the
`mvp/user-docs` submodule pointer in the parent MVP repository as a separate
change.

About 5 and 15 minutes after the **Mintlify Deployment** check succeeds, run
`scripts/verify_live_docs.sh`. It checks that every page serves the `sdkVersion`
in `docs.json` and every redirect returns 308, requesting each URL several times
because CDN edges can keep an old copy after a deploy. If a page stays stale, a
new commit on `main` redeploys the site.
