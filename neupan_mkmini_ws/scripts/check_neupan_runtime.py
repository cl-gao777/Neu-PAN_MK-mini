#!/usr/bin/env python3
import importlib
import pathlib
import platform
import sys


REQUIRED_MODULES = ("torch", "cvxpy", "cvxpylayers", "neupan")
CHECKPOINT_PLACEHOLDER = "REPLACE_WITH_TRAINED_MKMINI_DUNE_CHECKPOINT"


def workspace_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def main() -> int:
    failed = False
    print(f"Python: {sys.version.split()[0]}")
    print(f"Machine: {platform.machine()}")

    for module_name in REQUIRED_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception as error:
            failed = True
            print(f"MISSING {module_name}: {error}")
            continue
        version = getattr(module, "__version__", "unknown")
        print(f"OK {module_name}: {version}")

    if "--require-checkpoint" in sys.argv:
        config_path = (
            workspace_root()
            / "src"
            / "mkmini_neupan_bringup"
            / "config"
            / "neupan_mkmini.yaml"
        )
        config = config_path.read_text(encoding="utf-8")
        if CHECKPOINT_PLACEHOLDER in config:
            failed = True
            print(
                "MISSING trained MK-mini DUNE checkpoint in neupan_mkmini.yaml. "
                "Train MK-mini DUNE with wheelbase=0.6, length=0.84-0.90, "
                "width=0.60, then replace the dune_checkpoint placeholder."
            )

    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
