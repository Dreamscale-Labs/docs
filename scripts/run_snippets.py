#!/usr/bin/env python3
"""Run every Python snippet and check every CLI command on the published pages.

The docs are the spec: this script is how we know each snippet works as written.

Static mode (default, runs in CI, no network):
  * every `dreamscale ...` command, in code blocks and inline code, names a real
    command, and each of its options and choices appears in that command's --help;
  * every Python block runs against the installed SDK with synthetic observations,
    the real observation helpers and a stand-in `connect` that binds each call to
    the real signatures;
  * the Models table matches the SDK's model contracts.

Live mode (`--live dev|prod`, run by hand, needs DREAMSCALE_API_KEY):
  * every Python block that connects runs for real, one session at a time, and
    every session is closed before the next starts;
  * the account-only CLI commands run (`--version`, `models`, `doctor`), plus
    `sim libero` with `--sim`, and the install commands with `--uv`.

Hardware commands (`robots`, `run`, `doctor so101|yam`) are listed and checked
statically only: they need a real arm.
"""

from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "docs.json").read_text())
FENCE_RE = re.compile(
    r"^(?P<indent>[ \t]*)```(?P<lang>[A-Za-z0-9_+-]*)[^\n]*\n(?P<body>.*?)^[ \t]*```", re.M | re.S
)
INLINE_RE = re.compile(r"(?<!`)`(?P<code>(?:dreamscale|uv) [^`]+)`(?!`)")
CONNECT_RE = re.compile(r"""dreamscale\.a?connect\(\s*["'](?P<model>[^"']+)["']""")
ENDPOINTS = {"dev": "https://api-dev.dreamscalelabs.com", "prod": "https://api.dreamscalelabs.com"}
# Commands that need a robot on the bench. Checked against --help, never run here.
HARDWARE_PREFIXES = (("robots",), ("run",), ("doctor", "so101"), ("doctor", "yam"))
# Commands that need a browser, a Hugging Face repo or a deployment.
STATIC_ONLY_PREFIXES = (("login",), ("deployments",))
PLACEHOLDER_RE = re.compile(r"\.\.\.|^<.*>$|^ckpt_|://|^\.{1,2}/")  # also a local folder
# A deployment named by its slug, where the command takes one (its help says so).
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,46}[a-z0-9]")


@dataclass
class Snippet:
    page: str
    line: int
    lang: str
    code: str

    @property
    def label(self) -> str:
        return f"{self.page}:{self.line}"


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    rows: list[tuple[str, str, str]] = field(default_factory=list)

    def ok(self, label: str, what: str, detail: str = "") -> None:
        self.rows.append(("ok", label, f"{what} {detail}".strip()))

    def skip(self, label: str, what: str, why: str) -> None:
        self.rows.append(("skip", label, f"{what} ({why})"))

    def fail(self, label: str, what: str, why: str) -> None:
        self.rows.append(("FAIL", label, f"{what}: {why}"))
        self.failures.append(f"{label}: {what}: {why}")


def navigation_pages(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [page for item in node for page in navigation_pages(item)]
    if isinstance(node, dict):
        return navigation_pages(node.get("pages", []))
    return []


def extract(pages: list[str]) -> tuple[list[Snippet], list[Snippet]]:
    """Python blocks, and shell commands from bash blocks and inline code."""
    python: list[Snippet] = []
    commands: list[Snippet] = []
    for slug in pages:
        page = f"{slug}.mdx"
        text = (ROOT / page).read_text()
        fenced_spans = []
        for match in FENCE_RE.finditer(text):
            fenced_spans.append(match.span())
            line = text.count("\n", 0, match.start()) + 2
            lang = match.group("lang").lower()
            body = textwrap.dedent(match.group("body"))
            if lang in {"python", "py"}:
                python.append(Snippet(page, line, "python", body))
            elif lang in {"bash", "sh", "shell"}:
                for offset, raw in enumerate(body.splitlines()):
                    command = raw.split(" #", 1)[0].strip()
                    if command:
                        commands.append(Snippet(page, line + offset, "bash", command))
        for match in INLINE_RE.finditer(text):
            if any(start <= match.start() < end for start, end in fenced_spans):
                continue
            line = text.count("\n", 0, match.start()) + 1
            commands.append(Snippet(page, line, "inline", match.group("code").strip()))
    return python, commands


# ---------------------------------------------------------------- CLI checks


class Cli:
    """`dreamscale ... --help`, cached, with the command tree parsed from it."""

    def __init__(self) -> None:
        self._help: dict[tuple[str, ...], str | None] = {}

    def help(self, path: tuple[str, ...]) -> str | None:
        if path not in self._help:
            env = {**os.environ, "COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb",
                   "DREAMSCALE_SKIP_VERSION_CHECK": "1"}
            done = subprocess.run(
                [sys.executable, "-m", "dreamscale.cli", *path, "--help"],
                capture_output=True, text=True, env=env, check=False,
            )
            self._help[path] = done.stdout if done.returncode == 0 else None
        return self._help[path]

    def subcommands(self, path: tuple[str, ...]) -> set[str]:
        text = self.help(path) or ""
        section = text.split("Commands", 1)[1] if "Commands" in text else ""
        return set(re.findall(r"^│ ([a-z0-9][a-z0-9-]*)\s", section, re.M))

    def hidden_subcommand(self, path: tuple[str, ...], token: str) -> bool:
        """A command its group leaves out of --help (hidden until launch) still has its own."""
        parent = self.help(path) or ""
        if "Commands" not in parent or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", token):
            return False
        own = self.help((*path, token))
        return own is not None and own != parent


def check_cli(snippet: Snippet, cli: Cli, report: Report) -> tuple[str, ...] | None:
    try:
        tokens = shlex.split(snippet.code)
    except ValueError as error:
        report.fail(snippet.label, snippet.code, f"can't parse: {error}")
        return None
    if tokens[0] != "dreamscale":
        return None
    path: tuple[str, ...] = ()
    rest = tokens[1:]
    while rest and (rest[0] in cli.subcommands(path) or cli.hidden_subcommand(path, rest[0])):
        path += (rest.pop(0),)
    text = cli.help(path)
    if text is None:
        report.fail(snippet.label, snippet.code, f"`dreamscale {' '.join(path)} --help` failed")
        return None
    previous_was_option = False
    for token in rest:
        if token.startswith("-"):
            option = token.split("=", 1)[0]
            if not re.search(rf"(?<![\w-]){re.escape(option)}(?![\w-])", text):
                report.fail(snippet.label, snippet.code, f"{option} is not an option of "
                            f"`dreamscale {' '.join(path)}`")
            previous_was_option = "=" not in token
            continue
        if previous_was_option or PLACEHOLDER_RE.search(token):
            previous_was_option = False
            continue
        if "its slug" in text and SLUG_RE.fullmatch(token):
            continue
        # A positional choice, like `so101` in `doctor so101`, must appear in the help.
        if not re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", text):
            report.fail(snippet.label, snippet.code, f"`{token}` is not listed in "
                        f"`dreamscale {' '.join(path)} --help`")
    positional = tuple(t for t in rest if not t.startswith("-"))
    return path + positional


def kind_of(path: tuple[str, ...]) -> str:
    if any(path[: len(prefix)] == prefix for prefix in HARDWARE_PREFIXES):
        return "hardware"
    if any(path[: len(prefix)] == prefix for prefix in STATIC_ONLY_PREFIXES):
        return "static"
    return "live"


# ---------------------------------------------------------------- Python


class StopSnippet(Exception):
    """Raised by counted_next_action to end a `while True` control loop."""


def fixtures() -> dict[str, object]:
    """Synthetic values for the names a page tells the reader to fill in."""
    import numpy as np

    import dreamscale

    rng = np.random.default_rng(0)

    def frame(height: int = 480, width: int = 640) -> np.ndarray:
        return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)

    return {
        "dreamscale": dreamscale,
        # SO-101: calibrated LeRobot degrees, gripper 0-100.
        "side": frame(), "wrist": frame(),
        "joints": [0.0, -90.0, 90.0, 60.0, 0.0, 20.0],
        # Bimanual YAM: radians, grippers 0 closed to 1 open.
        "top": frame(), "left_wrist": frame(), "right_wrist": frame(),
        "left_joints": [0.0] * 6, "right_joints": [0.0] * 6,
        "left_gripper": 1.0, "right_gripper": 1.0,
        # LIBERO: raw 256 px renders; eef position, axis-angle, gripper qpos.
        "agent_view": frame(256, 256), "wrist_view": frame(256, 256),
        "state": [-0.2, 0.0, 1.17, 3.14, 0.0, 0.0, 0.04, -0.04],
    }


@contextlib.contextmanager
def counted_next_action(log: list[float], max_actions: int):
    """Time each next_action() and end a snippet's `while True` loop after max_actions."""
    import dreamscale

    inner = dreamscale.connect

    class Counted:
        def __init__(self, policy: object) -> None:
            self._policy = policy

        def __getattr__(self, name: str) -> object:
            return getattr(self._policy, name)

        def next_action(self, *args, **kwargs):
            if len(log) >= max_actions:
                raise StopSnippet
            action = self._policy.next_action(*args, **kwargs)
            log.append(time.perf_counter())
            return action

    def connect(*args, **kwargs):
        return Counted(inner(*args, **kwargs))

    dreamscale.connect = connect
    try:
        yield
    finally:
        dreamscale.connect = inner


@contextlib.contextmanager
def stand_in_connect(contracts: dict[str, tuple[int, int, float]]):
    """Replace dreamscale.connect with a policy that binds each call to the real API."""
    import typing

    import dreamscale

    real_connect = dreamscale.connect
    # Bind against the class connect() really returns (RemotePolicy up to a103, Policy after).
    try:
        RemotePolicy = typing.get_type_hints(real_connect)["return"]  # noqa: N806
    except Exception:  # noqa: BLE001 - unresolvable annotation: fall back to the old class
        from dreamscale.policy.remote import RemotePolicy

    class StandInPolicy:
        def __init__(self, model: str) -> None:
            self.model = model
            self.chunk, self.width, self.action_hz = contracts.get(model, (1, 6, 30.0))

        def _actions(self, observation) -> tuple[tuple[float, ...], ...]:
            hold = getattr(observation, "hold_action", None) or (0.0,) * self.width
            return tuple(tuple(hold) for _ in range(self.chunk))

        def predict(self, *args, **kwargs):
            inspect.signature(RemotePolicy.predict).bind(self, *args, **kwargs)
            return type("Chunk", (), {"actions": self._actions(args[0])})()

        def next_action(self, *args, **kwargs):
            inspect.signature(RemotePolicy.next_action).bind(self, *args, **kwargs)
            return self._actions(args[0])[0]

        def close(self) -> None:
            inspect.signature(RemotePolicy.close).bind(self)

    def connect(*args, **kwargs):
        inspect.signature(real_connect).bind(*args, **kwargs)
        return StandInPolicy(args[0] if args else kwargs["model"])

    dreamscale.connect = connect
    try:
        yield
    finally:
        dreamscale.connect = real_connect


def run_python(snippet: Snippet, *, live: bool, max_actions: int, report: Report,
               model_map: dict[str, str]) -> None:
    match = CONNECT_RE.search(snippet.code)
    code = snippet.code
    model = match.group("model") if match else None
    if model and model in model_map:
        code = code.replace(f'"{model}"', f'"{model_map[model]}"')
        model = model_map[model]
    if live and "ckpt_..." in code:
        report.skip(snippet.label, "python", "needs your own deployment")
        return
    log: list[float] = []
    namespace = fixtures()
    started = time.perf_counter()
    try:
        with counted_next_action(log, max_actions):
            exec(compile(code, snippet.label, "exec"), namespace)  # noqa: S102 - our own docs
    except StopSnippet:
        pass
    except Exception as error:  # noqa: BLE001 - every failure is a docs failure
        report.fail(snippet.label, f"python ({model or 'no model'})",
                    f"{type(error).__name__}: {error}")
        return
    finally:
        policy = namespace.get("policy")
        if live and policy is not None and hasattr(policy, "close"):
            with contextlib.suppress(Exception):
                policy.close()
    detail = f"{model or 'no model'}, {time.perf_counter() - started:.1f} s"
    if "chunk" in namespace:
        actions = namespace["chunk"].actions
        detail += f", chunk {len(actions)} x {len(actions[0])}"
    if len(log) > 1:
        gaps = [b - a for a, b in zip(log, log[1:])]
        steady = sorted(gaps[len(gaps) // 3:])  # skip the first chunk's arrival
        detail += (f", {len(log)} actions, median period "
                   f"{1000 * steady[len(steady) // 2]:.1f} ms")
    report.ok(snippet.label, "python", f"({detail})")


# ---------------------------------------------------------------- Models table


def check_models_table(report: Report) -> None:
    from dreamscale.policy.runtime.contract import runtime_contract_for_model

    text = (ROOT / "models.mdx").read_text()
    rows = re.findall(r"^\| `([a-z0-9.-]+)` \| [^|]+ \| (\d+) × (\d+) \| (\d+) Hz \|$", text, re.M)
    if not rows:
        report.fail("models.mdx", "Models table", "no rows found")
    for model, chunk, width, hz in rows:
        contract = runtime_contract_for_model(model)
        documented = (int(chunk), int(width), float(hz))
        actual = (contract.chunk_size, contract.action_dim, contract.action_hz)
        if documented != actual:
            report.fail("models.mdx", f"`{model}` row",
                        f"documents {documented}, SDK contract is {actual}")
        else:
            report.ok("models.mdx", f"`{model}` row", f"matches SDK {actual}")


def documented_contracts() -> dict[str, tuple[int, int, float]]:
    text = (ROOT / "models.mdx").read_text()
    return {m: (int(c), int(w), float(hz)) for m, c, w, hz in
            re.findall(r"^\| `([a-z0-9.-]+)` \| [^|]+ \| (\d+) × (\d+) \| (\d+) Hz \|", text, re.M)}


# ---------------------------------------------------------------- live CLI


def run_cli(argv: list[str], report: Report, label: str, *, timeout: float = 120,
            expect: str | None = None) -> None:
    """Run one command; with `expect`, its stdout must contain that line, as the page says."""
    started = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "-m", "dreamscale.cli", *argv], capture_output=True, text=True,
        timeout=timeout, check=False,
        env={**os.environ, "NO_COLOR": "1", "COLUMNS": "200"},
    )
    tail = (done.stdout + done.stderr).strip().splitlines()[-1:] or [""]
    what = "dreamscale " + " ".join(argv)
    if expect is not None:
        tail = [line for line in done.stdout.splitlines() if line.startswith("Using ")][:1]
        tail = [" / ".join(tail + [expect if expect in done.stdout else "no " + repr(expect)])]
        if expect not in done.stdout:
            report.fail(label, what, f"exit {done.returncode}: {tail[0][:200]}")
            return
    if done.returncode == 0:
        report.ok(label, what, f"({time.perf_counter() - started:.1f} s; {tail[0][:100]})")
    else:
        report.fail(label, what, f"exit {done.returncode}: {tail[0][:200]}")


def check_uv(report: Report) -> None:
    """`uv tool install`, `uv add` and the upgrade commands resolve the newest release."""
    import urllib.request

    with urllib.request.urlopen("https://pypi.org/pypi/dreamscale/json", timeout=20) as reply:
        latest = json.load(reply)["info"]["version"]
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "UV_TOOL_DIR": f"{tmp}/tools", "UV_TOOL_BIN_DIR": f"{tmp}/bin",
               "DREAMSCALE_SKIP_VERSION_CHECK": "1"}
        steps = [
            (["uv", "tool", "install", "dreamscale"], tmp),
            ([f"{tmp}/bin/dreamscale", "--version"], tmp),
            (["uv", "tool", "upgrade", "dreamscale"], tmp),
            (["uv", "init", "-q", "--no-workspace", "project"], tmp),
            (["uv", "add", "-q", "dreamscale"], f"{tmp}/project"),
            (["uv", "add", "-q", "dreamscale", "--upgrade-package", "dreamscale"], f"{tmp}/project"),
            (["uv", "run", "python", "-c", "import dreamscale; print(dreamscale.__version__)"],
             f"{tmp}/project"),
        ]
        for argv, cwd in steps:
            done = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                                  check=False, timeout=600)
            what = " ".join(argv).replace(tmp, "$TMP")
            output = (done.stdout + done.stderr).strip()
            if done.returncode != 0:
                report.fail("install", what, output.splitlines()[-1] if output else "failed")
                return
            if "--version" in argv or "__version__" in argv[-1]:
                version = output.split()[-1]
                if version != latest:
                    report.fail("install", what, f"got {version}, PyPI latest is {latest}")
                    continue
                report.ok("install", what, f"({version} = PyPI latest)")
            else:
                report.ok("install", what)


def live_home(env_name: str) -> str:
    """A throwaway DREAMSCALE_HOME pointing the SDK at the chosen control plane."""
    home = tempfile.mkdtemp(prefix="dreamscale-docs-")
    Path(home, "config.toml").write_text(f'[api]\ncontrol_plane_url = "{ENDPOINTS[env_name]}"\n')
    return home


# ---------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--live", choices=sorted(ENDPOINTS), help="also run against this env")
    parser.add_argument("--only", default="", help="only snippets whose page:line contains this")
    parser.add_argument("--max-actions", type=int, default=0,
                        help="actions before a control loop stops (static 5, live 150)")
    parser.add_argument("--model", action="append", default=[], metavar="DOCS=RUN",
                        help="run a snippet's model as another, e.g. pi0.5-so101=molmoact2-so101")
    parser.add_argument("--sim", action="store_true", help="live: also run `dreamscale sim libero`")
    parser.add_argument("--uv", action="store_true", help="also check the install commands")
    parser.add_argument("--skip-cli", action="store_true", help="live: skip account CLI commands")
    parser.add_argument("--any-version", action="store_true",
                        help="allow an installed SDK other than docs.json's sdkVersion")
    args = parser.parse_args()
    model_map = dict(item.split("=", 1) for item in args.model)
    max_actions = args.max_actions or (150 if args.live else 5)

    import dreamscale

    report = Report()
    expected = CONFIG["variables"]["sdkVersion"]
    if dreamscale.__version__ != expected and not args.any_version:
        report.fail("docs.json", "sdkVersion", f"docs say {expected}, installed "
                    f"dreamscale is {dreamscale.__version__} (pass --any-version to allow)")
    pages = navigation_pages(CONFIG["navigation"])
    python, commands = extract(pages)
    print(f"dreamscale {dreamscale.__version__}; {len(pages)} pages, {len(python)} Python "
          f"blocks, {len(commands)} commands" + (f"; live on {args.live}" if args.live else ""))

    cli = Cli()
    live_commands: list[tuple[Snippet, tuple[str, ...]]] = []
    for snippet in commands:
        if args.only not in snippet.label:
            continue
        path = check_cli(snippet, cli, report)
        if path is None:
            continue
        kind = kind_of(path)
        if kind == "live":
            live_commands.append((snippet, path))
        report.ok(snippet.label, snippet.code, f"(--help; {kind})")

    check_models_table(report)

    if args.live:
        if not os.environ.get("DREAMSCALE_API_KEY"):
            print("DREAMSCALE_API_KEY is not set. Load dev.env or test.env first.", file=sys.stderr)
            return 2
        os.environ["DREAMSCALE_HOME"] = live_home(args.live)
        os.environ["DREAMSCALE_SKIP_VERSION_CHECK"] = "1"
        for snippet in python:
            if args.only in snippet.label:
                run_python(snippet, live=True, max_actions=max_actions, report=report,
                           model_map=model_map)
        if not args.skip_cli:
            seen: set[tuple[str, ...]] = set()
            for snippet, path in live_commands:
                if path in seen or path[:2] == ("sim", "libero") and not args.sim:
                    continue
                seen.add(path)
                argv = shlex.split(snippet.code)[1:]
                expect = None
                if path[:2] == ("sim", "libero"):
                    # Headless here (no window); the page's success line must still print.
                    argv += ["--non-interactive"]
                    expect = "result: success condition reached"
                run_cli(argv, report, snippet.label, timeout=1800, expect=expect)
    else:
        with stand_in_connect(documented_contracts()):
            for snippet in python:
                if args.only in snippet.label:
                    run_python(snippet, live=False, max_actions=max_actions, report=report,
                               model_map=model_map)
    if args.uv:
        check_uv(report)

    for status, label, detail in report.rows:
        print(f"{status:<5} {label:<26} {detail}")
    if report.failures:
        print(f"\n{len(report.failures)} failed.", file=sys.stderr)
        return 1
    print("\nAll snippets passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
