#!/usr/bin/env python3
"""Verify documented Python and CLI surfaces against the configured package."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import dropbear
from dropbear import franka, libero, so101
from dropbear.policy import RemotePolicy


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "docs.json").read_text())
SDK_VERSION = CONFIG["variables"]["sdkVersion"]


def parameter_names(callable_object: object) -> tuple[str, ...]:
    return tuple(inspect.signature(callable_object).parameters)


def require_signature(
    label: str,
    callable_object: object,
    expected: tuple[str, ...],
) -> None:
    actual = parameter_names(callable_object)
    if actual != expected:
        raise AssertionError(f"{label} parameters changed: expected {expected}, got {actual}")


def cli_help(*arguments: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "dropbear.cli", *arguments, "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def require_words(label: str, text: str, expected: set[str]) -> None:
    missing = sorted(word for word in expected if word not in text)
    if missing:
        raise AssertionError(f"{label} help is missing: {', '.join(missing)}")


def main() -> int:
    if dropbear.__version__ != SDK_VERSION:
        raise AssertionError(
            f"docs configure dropbear {SDK_VERSION}, installed {dropbear.__version__}"
        )

    connect_parameters = (
        "model",
        "acceleration",
        "control",
        "rtc",
        "calibration",
        "region",
        "idle_timeout",
        "transport",
        "on_progress",
    )
    require_signature("dropbear.connect", dropbear.connect, connect_parameters)
    require_signature("dropbear.aconnect", dropbear.aconnect, connect_parameters)
    require_signature(
        "RemotePolicy.predict",
        RemotePolicy.predict,
        ("self", "observation", "instruction", "timeout_s"),
    )
    require_signature(
        "RemotePolicy.next_action",
        RemotePolicy.next_action,
        ("self", "observation", "instruction", "timeout_s"),
    )
    require_signature(
        "RemotePolicy.run",
        RemotePolicy.run,
        ("self", "instruction", "observe", "act", "max_actions", "strategy", "hooks"),
    )
    require_signature("RemotePolicy.close", RemotePolicy.close, ("self",))
    require_signature(
        "dropbear.so101.observe",
        so101.observe,
        ("side_frame", "wrist_frame", "frame", "joint_positions", "actions_remaining"),
    )
    require_signature(
        "dropbear.franka.observe",
        franka.observe,
        (
            "exterior_frame",
            "wrist_frame",
            "joint_positions",
            "gripper",
            "second_exterior_frame",
            "actions_remaining",
        ),
    )
    require_signature(
        "dropbear.libero.observe",
        libero.observe,
        ("agent_frame", "wrist_frame", "state", "actions_remaining"),
    )

    require_words(
        "dropbear",
        cli_help(),
        {"login", "doctor", "sim", "status", "sessions", "robots", "run"},
    )
    require_words("login", cli_help("login"), {"--api-key"})
    require_words("doctor", cli_help("doctor"), {"core", "so101", "sim", "all"})
    require_words(
        "sim",
        cli_help("sim"),
        {
            "--task-suite",
            "--task-id",
            "--max-steps",
            "--max-duration",
            "--non-interactive",
            "--transport",
            "--region",
        },
    )
    require_words("status", cli_help("status"), {"--model", "--region"})
    require_words("sessions", cli_help("sessions"), {"list", "stop"})
    require_words("sessions list", cli_help("sessions", "list"), {"--json"})
    require_words("sessions stop", cli_help("sessions", "stop"), {"--all", "SESSION_ID"})
    require_words("robots so101", cli_help("robots", "so101"), {"setup", "calibrate"})
    require_words(
        "run pick-place",
        cli_help("run", "pick-place"),
        {"--duration", "--fallback", "--no-fallback"},
    )

    print(f"SDK contract passed for dropbear {SDK_VERSION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
