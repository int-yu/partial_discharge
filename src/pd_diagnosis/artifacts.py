from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import ArtifactCompatibilityError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_bundle_artifact(root: Path, relative_name: object, field: str) -> Path:
    if not isinstance(relative_name, str) or not relative_name.strip():
        raise ArtifactCompatibilityError(f"{field} 必须是非空的相对路径字符串")

    relative_path = Path(relative_name)
    if relative_path.is_absolute():
        raise ArtifactCompatibilityError(f"{field} 必须位于模型 bundle 目录内")

    artifact = (root / relative_path).resolve()
    if not artifact.is_relative_to(root):
        raise ArtifactCompatibilityError(f"{field} 不能指向模型 bundle 目录外部")
    return artifact
