from __future__ import annotations

import json
import shutil

import pytest

from pd_diagnosis.bundle import ModelBundle
from pd_diagnosis.errors import ArtifactCompatibilityError


def test_bundle_rejects_feature_schema_mismatch(project_root, tmp_path):
    source = project_root / "models" / "default"
    target = tmp_path / "model"
    shutil.copytree(source, target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["feature_schema"] = "future-v2"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ArtifactCompatibilityError, match="特征版本不兼容"):
        ModelBundle.load(target)
