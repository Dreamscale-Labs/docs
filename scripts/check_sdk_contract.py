#!/usr/bin/env python3
"""Verify documented Python and CLI surfaces against the configured package."""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import dreamscale
from dreamscale import franka, libero, robot, so101, trossen, yam
from dreamscale.policy import RemotePolicy

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
    environment = os.environ.copy()
    environment.update(
        {
            "COLUMNS": "200",
            "FORCE_COLOR": "0",
            "NO_COLOR": "1",
            "TERM": "dumb",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-m", "dreamscale.cli", *arguments, "--help"],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    return completed.stdout


def require_words(label: str, text: str, expected: set[str]) -> None:
    missing = sorted(word for word in expected if word not in text)
    if missing:
        raise AssertionError(f"{label} help is missing: {', '.join(missing)}")


def main() -> int:
    if dreamscale.__version__ != SDK_VERSION:
        raise AssertionError(
            f"docs configure dreamscale {SDK_VERSION}, installed {dreamscale.__version__}"
        )

    connect_parameters = (
        "model",
        "acceleration",
        "control",
        "rtc",
        "calibration",
        "region",
        "provider",
        "speed",
        "idle_timeout",
        "keep_warm",
        "startup_timeout",
        "transport",
        "control_hz",
        "deployment",
        "checkpoint",
        "endpoint",
        "api_key",
        "context",
        "on_progress",
    )
    require_signature("dreamscale.connect", dreamscale.connect, connect_parameters)
    require_signature("dreamscale.aconnect", dreamscale.aconnect, connect_parameters)
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
        (
            "self",
            "instruction",
            "observe",
            "act",
            "read_hold_action",
            "max_actions",
            "strategy",
            "hooks",
        ),
    )
    require_signature("RemotePolicy.close", RemotePolicy.close, ("self",))
    require_signature(
        "dreamscale.so101.observe",
        so101.observe,
        ("side_frame", "wrist_frame", "frame", "joint_positions", "actions_remaining"),
    )
    require_signature(
        "dreamscale.franka.observe",
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
        "dreamscale.libero.observe",
        libero.observe,
        ("agent_frame", "wrist_frame", "state", "actions_remaining", "model"),
    )

    for name, helper in (("yam", yam.observe), ("trossen", trossen.observe)):
        documented = {
            "yam": ("top_frame", "left_frame", "right_frame"),
            "trossen": ("left_wrist_frame", "high_frame", "right_wrist_frame"),
        }[name] + (
            "left_joint_positions",
            "left_gripper",
            "right_joint_positions",
            "right_gripper",
        )
        missing = set(documented) - set(parameter_names(helper))
        if missing:
            raise AssertionError(f"dreamscale.{name}.observe lost parameters: {sorted(missing)}")
    require_signature(
        "dreamscale.robot.observe",
        robot.observe,
        ("cameras", "state", "actions_remaining"),
    )

    require_words(
        "dreamscale",
        cli_help(),
        {
            "login",
            "doctor",
            "sim",
            "models",
            "sessions",
            "robots",
            "run",
            "deployments",
            "integrations",
        },
    )
    require_words("login", cli_help("login"), {"--api-key"})
    require_words("doctor", cli_help("doctor"), {"core", "so101", "yam", "sim", "all", "--model"})
    require_words(
        "sim",
        cli_help("sim"),
        {
            "libero",
            "--model",
            "--keep-warm",
            "--output-root",
            "--task-suite",
            "--task-id",
            "--max-steps",
            "--max-duration",
            "--non-interactive",
            "--transport",
            "--region",
        },
    )
    require_words("models", cli_help("models"), {"--verbose", "--json"})
    require_words("sessions", cli_help("sessions"), {"list", "stop"})
    require_words("sessions list", cli_help("sessions", "list"), {"--json"})
    require_words("sessions stop", cli_help("sessions", "stop"), {"--all", "SESSION_ID"})
    require_words(
        "robots so101", cli_help("robots", "so101"), {"setup", "calibrate", "home", "release"}
    )
    require_words("robots yam", cli_help("robots", "yam"), {"setup", "home", "release"})
    require_words("robots yam setup", cli_help("robots", "yam", "setup"), {"--cli", "--config"})
    require_words("robots so101 home", cli_help("robots", "so101", "home"), {"--set"})
    run_options = {
        "--model",
        "--instruction",
        "--max-actions",
        "--keep-warm",
        "--mode",
        "--deployment",
        "--speed",
        "--region",
        "--max-joint-step",
        "--max-joint-velocity",
        "--effort",
        "--max-cost",
        "--hud",
        "--hud-job",
        "--inspect-robots",
        "--task",
        "--epochs",
        "--log-dir",
        "--trace-dir",
        "--trace-images",
    }
    require_words("run so101", cli_help("run", "so101"), run_options)
    require_words("run yam", cli_help("run", "yam"), run_options | {"--config"})
    require_words("integrations", cli_help("integrations"), {"hud", "inspect-robots"})
    require_words("integrations hud setup", cli_help("integrations", "hud", "setup"), {"--api-key"})
    require_words(
        "deployments",
        cli_help("deployments"),
        {"create", "inspect", "list", "show", "keep-warm", "restore", "rm"},
    )
    require_words(
        "deployments create",
        cli_help("deployments", "create"),
        {
            "--preset",
            "--region",
            "--camera",
            "--image-size",
            "--dataset",
            "--action-dim",
            "--state-dim",
            "--chunk",
            "--hz",
            "--context",
            "--revision",
            "--hf-token",
            "--no-wait",
        },
    )
    require_words(
        "deployments keep-warm",
        cli_help("deployments", "keep-warm"),
        {"--take-over-from", "always"},
    )

    print(f"SDK contract passed for dreamscale {SDK_VERSION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
