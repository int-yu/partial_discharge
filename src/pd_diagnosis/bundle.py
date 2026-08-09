from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .errors import ArtifactCompatibilityError
from .features import FEATURE_NAMES, FEATURE_SCHEMA
from .types import Pathish


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

    @classmethod
    def load(cls, path: Pathish) -> "ModelBundle":
        root = Path(path).expanduser().resolve()
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise ArtifactCompatibilityError(f"模型清单不存在：{manifest_path}")
        try:
            manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ArtifactCompatibilityError(f"无法读取模型清单：{exc}") from exc

        if manifest.get("schema_version") != 1:
            raise ArtifactCompatibilityError("不支持的模型 bundle 版本")
        if manifest.get("feature_schema") != FEATURE_SCHEMA:
            raise ArtifactCompatibilityError(
                f"特征版本不兼容：{manifest.get('feature_schema')!r}，需要 {FEATURE_SCHEMA!r}"
            )
        if manifest.get("feature_names") != list(FEATURE_NAMES):
            raise ArtifactCompatibilityError("模型特征顺序与当前 SDK 不一致")

        weights_path = root / str(manifest.get("weights_file", "weights.pth"))
        scaler_path = root / str(manifest.get("scaler_file", "scaler.npz"))
        for artifact, expected_hash in (
            (weights_path, manifest.get("weights_sha256")),
            (scaler_path, manifest.get("scaler_sha256")),
        ):
            if not artifact.is_file():
                raise ArtifactCompatibilityError(f"模型工件不存在：{artifact}")
            if expected_hash and _sha256(artifact) != expected_hash:
                raise ArtifactCompatibilityError(f"模型工件校验失败：{artifact.name}")

        try:
            with np.load(scaler_path, allow_pickle=False) as scaler:
                mean = np.asarray(scaler["mean"], dtype=np.float64)
                scale = np.asarray(scaler["scale"], dtype=np.float64)
        except (OSError, KeyError, ValueError) as exc:
            raise ArtifactCompatibilityError(f"标准化参数无效：{exc}") from exc
        if mean.shape != (len(FEATURE_NAMES),) or scale.shape != mean.shape:
            raise ArtifactCompatibilityError("标准化参数维度必须为 10")
        if np.any(scale == 0) or not np.all(np.isfinite(mean)) or not np.all(np.isfinite(scale)):
            raise ArtifactCompatibilityError("标准化参数包含无效数值")

        try:
            classes = tuple(
                ClassDefinition(id=int(item["id"]), name=str(item["name"]))
                for item in manifest["classes"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ArtifactCompatibilityError("类别清单格式无效") from exc
        if [item.id for item in classes] != list(range(len(classes))):
            raise ArtifactCompatibilityError("类别 ID 必须从 0 连续排列")

        return cls(
            root=root,
            model_version=str(manifest["model_version"]),
            feature_schema=str(manifest["feature_schema"]),
            sampling_rate_hz=int(manifest["sampling_rate_hz"]),
            min_samples=int(manifest.get("min_samples", 100)),
            classes=classes,
            weights_path=weights_path,
            scaler_path=scaler_path,
            scaler_mean=mean,
            scaler_scale=scale,
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
