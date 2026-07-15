from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .yaml_compat import safe_load


@dataclass(frozen=True)
class NeuPANConfigPaths:
    robot_config: Path
    robot_config_dir: Path
    planner_config: Path
    dune_checkpoint: Path


def parse_robot_parameters(config_text: str) -> dict[str, Any]:
    document = safe_load(config_text)
    if not isinstance(document, Mapping):
        raise ValueError("robot config must be a YAML mapping")

    parameters = None
    for node_config in document.values():
        if isinstance(node_config, Mapping) and isinstance(
            node_config.get("ros__parameters"), Mapping
        ):
            parameters = dict(node_config["ros__parameters"])
            break
    if parameters is None:
        raise ValueError("robot config is missing ros__parameters")

    for name in ("planner_config_file", "dune_checkpoint_file"):
        value = parameters.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"robot config is missing {name}")
    return parameters


def resolve_config_path(value: str, robot_config_dir: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else robot_config_dir / path


def load_neupan_config_paths(robot_config: Path) -> NeuPANConfigPaths:
    robot_config = Path(robot_config).expanduser()
    if not robot_config.is_file():
        raise ValueError(f"robot config file does not exist: {robot_config}")

    parameters = parse_robot_parameters(robot_config.read_text(encoding="utf-8"))
    robot_config_dir = robot_config.parent
    planner_config = resolve_config_path(
        parameters["planner_config_file"], robot_config_dir
    )
    dune_checkpoint = resolve_config_path(
        parameters["dune_checkpoint_file"], robot_config_dir
    )
    if not planner_config.is_file():
        raise ValueError(f"planner config file does not exist: {planner_config}")
    if not dune_checkpoint.is_file():
        raise ValueError(f"DUNE checkpoint file does not exist: {dune_checkpoint}")
    return NeuPANConfigPaths(
        robot_config=robot_config,
        robot_config_dir=robot_config_dir,
        planner_config=planner_config,
        dune_checkpoint=dune_checkpoint,
    )
