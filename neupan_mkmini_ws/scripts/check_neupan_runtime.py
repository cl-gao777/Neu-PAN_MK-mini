#!/usr/bin/env python3
import argparse
import pathlib
import platform
import sys


def workspace_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


sys.path.insert(0, str(workspace_root() / "src" / "mkmini_neupan_bringup"))

from mkmini_neupan_bringup.thor_neupan_preflight_node import (  # noqa: E402
    check_cvxpylayer_autograd,
    check_neupan_config,
    check_python_modules,
    check_thor_runtime_manifest,
)


def default_config_path() -> pathlib.Path:
    return (
        workspace_root()
        / "src"
        / "mkmini_neupan_bringup"
        / "config"
        / "robots"
        / "mkmini"
        / "robot.yaml"
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Check the Thor NeuPAN Python runtime.")
    parser.add_argument("--runtime-manifest", type=pathlib.Path, default=None)
    parser.add_argument(
        "--torch-lock-only",
        action="store_true",
        help="Only verify installed torch against the repository runtime lock.",
    )
    parser.add_argument("--neupan-config", type=pathlib.Path, default=None)
    parser.add_argument("--require-checkpoint", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Machine: {platform.machine()}")
    results = check_thor_runtime_manifest(args.runtime_manifest)
    if args.torch_lock_only:
        for result in results:
            print(f"{result.status} {result.name}: {result.detail}")
        return int(any(result.failed for result in results))
    results.extend(check_python_modules())
    results.append(check_cvxpylayer_autograd())
    if args.require_checkpoint or args.neupan_config is not None:
        results.extend(check_neupan_config(args.neupan_config or default_config_path()))
    for result in results:
        print(f"{result.status} {result.name}: {result.detail}")
    return int(any(result.failed for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
