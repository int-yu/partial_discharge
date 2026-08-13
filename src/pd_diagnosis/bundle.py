from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .artifacts import resolve_bundle_artifact, sha256_file
from .errors import ArtifactCompatibilityError
from .features import FEATURE_NAMES, FEATURE_SCHEMA
from .types import Pathish

SUPPORTED_ARCHITECTURE = "classification-mlp-v1"
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")


@dataclass(frozen=True, slots=True)
class ClassDefinition:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class ModelBundle:
    root: Path
    model_version: str
    feature_schema: str
    sampling_rate_hz: int
    min_samples: int
    classes: tuple[ClassDefinition, ...]
    weights_path: Path
    scaler_path: Path
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    confidence_warning_threshold: float

    @classmethod
    def load(cls, path: Pathish) -> "ModelBundle":
        root = Path(path).expanduser().resolve()
        manifest = _read_manifest(root / "manifest.json")

        if _required_integer(manifest, "schema_version") != 1:
            raise ArtifactCompatibilityError("schema_version：不支持的模型 bundle 版本")
        architecture = _required_string(manifest, "architecture")
        if architecture != SUPPORTED_ARCHITECTURE:
            raise ArtifactCompatibilityError(
                f"architecture 不受支持：{architecture!r}，需要 {SUPPORTED_ARCHITECTURE!r}"
            )

        feature_schema = _required_string(manifest, "feature_schema")
        if feature_schema != FEATURE_SCHEMA:
            raise ArtifactCompatibilityError(
                f"特征版本不兼容：{feature_schema!r}，需要 {FEATURE_SCHEMA!r}"
            )
        feature_names = manifest.get("feature_names")
        if (
            not isinstance(feature_names, list)
            or not all(isinstance(name, str) for name in feature_names)
            or feature_names != list(FEATURE_NAMES)
        ):
            raise ArtifactCompatibilityError("feature_names 与当前 SDK 特征版本不兼容")

        model_version = _required_string(manifest, "model_version")
        sampling_rate_hz = _required_positive_integer(manifest, "sampling_rate_hz")
        min_samples = _required_positive_integer(manifest, "min_samples")
        classes = _parse_classes(manifest.get("classes"))
        confidence_threshold = _confidence_threshold(manifest)

        weights_path = resolve_bundle_artifact(
            root, manifest.get("weights_file"), "weights_file"
        )
        scaler_path = resolve_bundle_artifact(
            root, manifest.get("scaler_file"), "scaler_file"
        )
        _verify_artifact(weights_path, manifest.get("weights_sha256"), "weights_sha256")
        _verify_artifact(scaler_path, manifest.get("scaler_sha256"), "scaler_sha256")

        mean, scale = _load_scaler(scaler_path)
        return cls(
            root=root,
            model_version=model_version,
            feature_schema=feature_schema,
            sampling_rate_hz=sampling_rate_hz,
            min_samples=min_samples,
            classes=classes,
            weights_path=weights_path,
            scaler_path=scaler_path,
            scaler_mean=mean,
            scaler_scale=scale,
            confidence_warning_threshold=confidence_threshold,
        )


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ArtifactCompatibilityError(f"模型清单不存在：{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ArtifactCompatibilityError(f"无法读取模型清单：{exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactCompatibilityError("模型清单顶层必须是 JSON 对象")
    return value


def _required_string(manifest: dict[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ArtifactCompatibilityError(f"{field} 必须是非空字符串")
    return value


def _required_integer(manifest: dict[str, Any], field: str) -> int:
    value = manifest.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactCompatibilityError(f"{field} 必须是整数")
    return value


def _required_positive_integer(manifest: dict[str, Any], field: str) -> int:
    value = _required_integer(manifest, field)
    if value <= 0:
        raise ArtifactCompatibilityError(f"{field} 必须大于 0")
    return value


def _required_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ArtifactCompatibilityError(f"{field} 必须是 64 位 SHA-256 十六进制字符串")
    return value.lower()


def _verify_artifact(path: Path, expected_value: object, hash_field: str) -> None:
    expected_hash = _required_sha256(expected_value, hash_field)
    if not path.is_file():
        raise ArtifactCompatibilityError(f"模型工件不存在：{path}")
    try:
        actual_hash = sha256_file(path)
    except OSError as exc:
        raise ArtifactCompatibilityError(f"无法读取模型工件：{path.name}：{exc}") from exc
    if actual_hash != expected_hash:
        raise ArtifactCompatibilityError(f"模型工件校验失败：{path.name}")


def _parse_classes(value: object) -> tuple[ClassDefinition, ...]:
    if not isinstance(value, list) or not value:
        raise ArtifactCompatibilityError("类别清单必须是非空列表")

    classes: list[ClassDefinition] = []
    names: set[str] = set()
    for expected_id, item in enumerate(value):
        if not isinstance(item, dict):
            raise ArtifactCompatibilityError("类别清单中的每一项必须是对象")
        class_id = item.get("id")
        name = item.get("name")
        if isinstance(class_id, bool) or not isinstance(class_id, int):
            raise ArtifactCompatibilityError("类别 id 必须是整数")
        if class_id != expected_id:
            raise ArtifactCompatibilityError("类别 ID 必须从 0 连续排列")
        if not isinstance(name, str) or not name.strip():
            raise ArtifactCompatibilityError("类别名称必须是非空字符串")
        if name in names:
            raise ArtifactCompatibilityError(f"类别名称不能重复：{name}")
        names.add(name)
        classes.append(ClassDefinition(id=class_id, name=name))
    return tuple(classes)


def _confidence_threshold(manifest: dict[str, Any]) -> float:
    value = manifest.get("confidence_warning_threshold", 0.6)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArtifactCompatibilityError(
            "confidence_warning_threshold 必须是 0.0 到 1.0 之间的数值"
        )
    threshold = float(value)
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ArtifactCompatibilityError(
            "confidence_warning_threshold 必须位于 [0.0, 1.0]"
        )
    return threshold


def _load_scaler(path: Path) -> tuple[np.ndarray, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as scaler:
            mean = np.asarray(scaler["mean"], dtype=np.float64)
            scale = np.asarray(scaler["scale"], dtype=np.float64)
    except (OSError, KeyError, ValueError) as exc:
        raise ArtifactCompatibilityError(f"标准化参数无效：{exc}") from exc
    if mean.shape != (len(FEATURE_NAMES),) or scale.shape != mean.shape:
        raise ArtifactCompatibilityError(
            f"标准化参数维度必须为 {len(FEATURE_NAMES)}"
        )
    if (
        not np.all(np.isfinite(mean))
        or not np.all(np.isfinite(scale))
        or np.any(scale <= 0)
    ):
        raise ArtifactCompatibilityError("标准化参数必须有限，且 scale 必须全部大于 0")
    return mean, scale
