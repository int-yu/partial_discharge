from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Sequence

import numpy as np

from .artifacts import sha256_file
from .features import FEATURE_NAMES, FEATURE_SCHEMA

DEFAULT_CLASSES = (
    "金属突出物缺陷",
    "自由微粒缺陷",
    "绝缘子表面金属污染物缺陷",
    "气隙缺陷",
)


def migrate_legacy_bundle(
    weights_path: str | Path,
    scaler_path: str | Path,
    output_dir: str | Path,
    *,
    trusted: bool = False,
) -> Path:
    if not trusted:
        raise ValueError("旧 scaler.pkl 可能执行任意代码；仅可信文件可设置 trusted=True")
    try:
        import joblib
    except ImportError as exc:
        raise RuntimeError("迁移旧模型需要安装 train 可选依赖") from exc

    source_weights = Path(weights_path).resolve()
    source_scaler = Path(scaler_path).resolve()
    target = Path(output_dir).resolve()
    if not source_weights.is_file() or not source_scaler.is_file():
        raise FileNotFoundError("旧模型权重或标准化器不存在")
    scaler = joblib.load(source_scaler)
    mean = np.asarray(getattr(scaler, "mean_", None), dtype=np.float64)
    scale = np.asarray(getattr(scaler, "scale_", None), dtype=np.float64)
    if mean.shape != (10,) or scale.shape != (10,):
        raise ValueError("旧标准化器必须包含 10 个特征")

    target.mkdir(parents=True, exist_ok=True)
    target_weights = target / "weights.pth"
    target_scaler = target / "scaler.npz"
    shutil.copy2(source_weights, target_weights)
    np.savez(target_scaler, mean=mean, scale=scale)
    manifest = {
        "schema_version": 1,
        "model_version": "legacy-2025-12-30",
        "architecture": "classification-mlp-v1",
        "feature_schema": FEATURE_SCHEMA,
        "feature_names": list(FEATURE_NAMES),
        "sampling_rate_hz": 1_000_000,
        "min_samples": 100,
        "confidence_warning_threshold": 0.6,
        "classes": [{"id": index, "name": name} for index, name in enumerate(DEFAULT_CLASSES)],
        "weights_file": target_weights.name,
        "weights_sha256": sha256_file(target_weights),
        "scaler_file": target_scaler.name,
        "scaler_sha256": sha256_file(target_scaler),
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="将可信旧模型迁移为版本化 bundle")
    parser.add_argument("weights")
    parser.add_argument("scaler")
    parser.add_argument("output")
    parser.add_argument("--trusted", action="store_true")
    args = parser.parse_args(argv)
    target = migrate_legacy_bundle(args.weights, args.scaler, args.output, trusted=args.trusted)
    print(f"模型已迁移到 {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
