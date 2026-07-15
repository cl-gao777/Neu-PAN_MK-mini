from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping

from .yaml_compat import safe_load


@dataclass(frozen=True)
class Transform:
    translation: tuple[float, float, float]
    quaternion: tuple[float, float, float, float]


@dataclass(frozen=True)
class FastLioTfConfig:
    calibrated: bool
    odom_frame: str
    camera_init_frame: str
    body_frame: str
    base_frame: str
    lidar_frame: str
    base_to_livox: Transform
    body_to_base: Transform


def quaternion_from_rpy(
    roll: float, pitch: float, yaw: float
) -> tuple[float, float, float, float]:
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def _rotate_by_quaternion(
    vector: tuple[float, float, float],
    quaternion: tuple[float, float, float, float],
) -> tuple[float, float, float]:
    x, y, z, w = quaternion
    vx, vy, vz = vector
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def inverse_transform(
    translation: tuple[float, float, float],
    rpy: tuple[float, float, float],
) -> Transform:
    quaternion = quaternion_from_rpy(*rpy)
    inverse_quaternion = (-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3])
    inverse_translation = _rotate_by_quaternion(
        (-translation[0], -translation[1], -translation[2]),
        inverse_quaternion,
    )
    return Transform(inverse_translation, inverse_quaternion)


def parse_fast_lio_tf(
    document: Mapping[str, object], require_calibrated: bool = False
) -> FastLioTfConfig:
    calibrated = document.get("calibrated") is True
    if require_calibrated and not calibrated:
        raise ValueError("FAST-LIO TF config must be calibrated before publication")

    frames = document.get("frames")
    measured = document.get("base_to_livox")
    if not isinstance(frames, Mapping):
        raise ValueError("FAST-LIO TF config is missing frames")
    if not isinstance(measured, Mapping):
        raise ValueError("FAST-LIO TF config is missing base_to_livox")

    frame_values = {}
    for key in ("odom", "camera_init", "body", "base", "lidar"):
        value = frames.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"FAST-LIO TF frame {key} must be non-empty")
        frame_values[key] = value

    values = []
    for key in ("x", "y", "z", "roll", "pitch", "yaw"):
        value = measured.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"FAST-LIO TF value {key} must be finite")
        values.append(float(value))
    translation = tuple(values[:3])
    rpy = tuple(values[3:])
    base_to_livox = Transform(translation, quaternion_from_rpy(*rpy))
    return FastLioTfConfig(
        calibrated=calibrated,
        odom_frame=frame_values["odom"],
        camera_init_frame=frame_values["camera_init"],
        body_frame=frame_values["body"],
        base_frame=frame_values["base"],
        lidar_frame=frame_values["lidar"],
        base_to_livox=base_to_livox,
        body_to_base=inverse_transform(translation, rpy),
    )


def load_fast_lio_tf(
    config_path: Path, require_calibrated: bool = False
) -> FastLioTfConfig:
    path = Path(config_path).expanduser()
    if not path.is_file():
        raise ValueError(f"FAST-LIO TF config does not exist: {path}")
    document = safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise ValueError("FAST-LIO TF config must be a YAML mapping")
    return parse_fast_lio_tf(document, require_calibrated=require_calibrated)
