from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from pd_diagnosis.bundle import ModelBundle
from pd_diagnosis.errors import ArtifactCompatibilityError


def _copy_bundle(project_root: Path, tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    target = tmp_path / "model"
    shutil.copytree(project_root / "models" / "default", target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return target, manifest_path, manifest


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bundle_rejects_feature_schema_mismatch(project_root, tmp_path):
    target, manifest_path, manifest = _copy_bundle(project_root, tmp_path)
    manifest["feature_schema"] = "future-v2"
    _write_manifest(manifest_path, manifest)

    with pytest.raises(ArtifactCompatibilityError, match="特征版本不兼容"):
        ModelBundle.load(target)


@pytest.mark.parametrize("field", ["weights_sha256", "scaler_sha256"])
def test_bundle_requires_artifact_hashes(project_root, tmp_path, field):
    target, manifest_path, manifest = _copy_bundle(project_root, tmp_path)
    manifest.pop(field)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(ArtifactCompatibilityError, match=field):
        ModelBundle.load(target)


def test_bundle_rejects_unsupported_architecture(project_root, tmp_path):
    target, manifest_path, manifest = _copy_bundle(project_root, tmp_path)
    manifest["architecture"] = "unknown-network-v9"
    _write_manifest(manifest_path, manifest)

    with pytest.raises(ArtifactCompatibilityError, match="architecture"):
        ModelBundle.load(target)


def test_bundle_rejects_artifact_path_traversal(project_root, tmp_path):
    target, manifest_path, manifest = _copy_bundle(project_root, tmp_path)
    escaped_weights = tmp_path / "escaped.pth"
    shutil.copy2(target / "weights.pth", escaped_weights)
    manifest["weights_file"] = "../escaped.pth"
    manifest["weights_sha256"] = _sha256(escaped_weights)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(ArtifactCompatibilityError, match="weights_file"):
        ModelBundle.load(target)


@pytest.mark.parametrize(
    "classes",
    [
        [],
        [{"id": 0, "name": "重复"}, {"id": 1, "name": "重复"}],
        [{"id": 0, "name": "   "}],
        [{"id": 1, "name": "不连续"}],
    ],
)
def test_bundle_rejects_invalid_classes(project_root, tmp_path, classes):
    target, manifest_path, manifest = _copy_bundle(project_root, tmp_path)
    manifest["classes"] = classes
    _write_manifest(manifest_path, manifest)

    with pytest.raises(ArtifactCompatibilityError, match="类别"):
        ModelBundle.load(target)


@pytest.mark.parametrize("bad_scale", [-1.0, 0.0, float("nan")])
def test_bundle_requires_strictly_positive_finite_scale(
    project_root, tmp_path, bad_scale
):
    target, manifest_path, manifest = _copy_bundle(project_root, tmp_path)
    scaler_path = target / "scaler.npz"
    with np.load(scaler_path, allow_pickle=False) as scaler:
        mean = np.asarray(scaler["mean"], dtype=np.float64)
        scale = np.asarray(scaler["scale"], dtype=np.float64)
    scale[0] = bad_scale
    np.savez(scaler_path, mean=mean, scale=scale)
    manifest["scaler_sha256"] = _sha256(scaler_path)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(ArtifactCompatibilityError, match="标准化参数"):
        ModelBundle.load(target)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_version", ""),
        ("sampling_rate_hz", "fast"),
        ("sampling_rate_hz", 0),
        ("min_samples", True),
        ("weights_file", 42),
        ("feature_names", "not-a-list"),
    ],
)
def test_bundle_rejects_malformed_required_fields(
    project_root, tmp_path, field, value
):
    target, manifest_path, manifest = _copy_bundle(project_root, tmp_path)
    manifest[field] = value
    _write_manifest(manifest_path, manifest)

    with pytest.raises(ArtifactCompatibilityError, match=field):
        ModelBundle.load(target)


def test_bundle_defaults_confidence_threshold_for_schema_v1(project_root):
    bundle = ModelBundle.load(project_root / "models" / "default")

    assert bundle.confidence_warning_threshold == pytest.approx(0.6)


@pytest.mark.parametrize("threshold", [-0.01, 1.01, True, "high"])
def test_bundle_rejects_invalid_confidence_threshold(
    project_root, tmp_path, threshold
):
    target, manifest_path, manifest = _copy_bundle(project_root, tmp_path)
    manifest["confidence_warning_threshold"] = threshold
    _write_manifest(manifest_path, manifest)

    with pytest.raises(ArtifactCompatibilityError, match="confidence_warning_threshold"):
        ModelBundle.load(target)
