#!/usr/bin/env python3
"""Fail CI when launch docs drift outside the supported public surface."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_CONFIG = ROOT / "docs.json"
FENCE_RE = re.compile(
    r"```(?P<language>[A-Za-z0-9_+-]+)(?:[^\n]*)\n(?P<body>.*?)```",
    re.DOTALL,
)
VARIABLE_RE = re.compile(r"\{\{(?P<name>[A-Za-z][A-Za-z0-9]*)\}\}")
FORBIDDEN_TEXT = {
    "Mintlify Starter Kit": "starter branding",
    "hi@mintlify.com": "starter support address",
    "app.mintlify.com": "starter dashboard link",
    "mintlify.com/blog": "starter blog link",
    "https://dropbear.dreamscalelabs.com/docs": "stale documentation domain",
}
STAGED_MODEL_MARKERS = (
    "bimanual-yam",
    "bimanualyam",
    "gr00t",
    "groot",
    "pi05",
)


def _navigation_pages(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [page for item in node for page in _navigation_pages(item)]
    if isinstance(node, dict):
        return _navigation_pages(node.get("pages", []))
    return []


def _frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    return text[4:end]


def _python_blocks(path: Path, text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(FENCE_RE.finditer(text), start=1):
        if match.group("language").lower() in {"python", "py"}:
            blocks.append((f"{path.relative_to(ROOT)} block {index}", match.group("body")))
    return blocks


def main() -> int:
    config = json.loads(DOCS_CONFIG.read_text())
    variables = set(config.get("variables", {}))
    pages = _navigation_pages(config.get("navigation", {}))
    errors: list[str] = []

    for slug in pages:
        path = ROOT / f"{slug}.mdx"
        if not path.exists():
            errors.append(f"{path.relative_to(ROOT)}: navigation target is missing")
            continue
        frontmatter = _frontmatter(path.read_text())
        if frontmatter is None:
            errors.append(f"{path.relative_to(ROOT)}: missing frontmatter")
            continue
        for key in ("title", "description", "keywords"):
            if not re.search(rf"(?m)^{key}:\s*\S", frontmatter):
                errors.append(f"{path.relative_to(ROOT)}: missing frontmatter {key}")

    content_paths = sorted(ROOT.rglob("*.mdx"))
    supporting_paths = [ROOT / "README.md", ROOT / "AGENTS.md", DOCS_CONFIG]
    for path in [*content_paths, *supporting_paths]:
        text = path.read_text()
        relative = path.relative_to(ROOT)
        for marker, description in FORBIDDEN_TEXT.items():
            if marker.lower() in text.lower():
                errors.append(f"{relative}: contains {description}: {marker!r}")
        for variable in VARIABLE_RE.findall(text):
            if variable not in variables:
                errors.append(f"{relative}: unknown docs variable {variable!r}")

    for path in content_paths:
        text = path.read_text()
        relative = path.relative_to(ROOT)
        lowered = text.lower()
        if re.search(r"(?<![a-z0-9])/v1(?:/|\b)", lowered):
            errors.append(f"{relative}: documents an internal API path")
        for marker in STAGED_MODEL_MARKERS:
            if marker in lowered:
                errors.append(f"{relative}: mentions staged model {marker!r}")

        for label, code in _python_blocks(path, text):
            try:
                ast.parse(code, filename=label)
            except SyntaxError as exc:
                errors.append(f"{label}: invalid Python: {exc.msg} (line {exc.lineno})")

        for match in FENCE_RE.finditer(text):
            language = match.group("language").lower()
            body = match.group("body")
            if language in {"python", "py"} and (
                "dropbear.connect_so101(" in body
                or re.search(r"\bconnect_so101\s*\(", body)
            ):
                errors.append(
                    f"{relative}: deprecated connect_so101 appears in a Python example"
                )

    if "{{sdkVersion}}" not in (ROOT / "quickstart.mdx").read_text():
        errors.append("quickstart.mdx: primary install example must use sdkVersion")
    if "team@dreamscalelabs.com" not in DOCS_CONFIG.read_text():
        errors.append("docs.json: support email is missing")
    if "https://docs.dropbear.dreamscalelabs.com" not in DOCS_CONFIG.read_text():
        errors.append("docs.json: canonical docs URL is missing")

    if errors:
        print("Documentation content guard failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Content guard passed: {len(pages)} pages, "
        f"{sum(len(_python_blocks(path, path.read_text())) for path in content_paths)} "
        "Python blocks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
