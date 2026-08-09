from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import torch

from .bundle import ModelBundle
from .errors import ArtifactCompatibilityError, DiagnosisError, InvalidSignalError
from .features import FEATURE_NAMES, extract_feature_vector, feature_mapping
from .model import ClassificationModel
from .signal_io import read_txt_signal
from .types import (
    BatchDiagnosisItem,
    BatchDiagnosisResult,
    DiagnosisResult,
    Pathish,
    Signal,
)


class DiagnosisEngine:
    """Thread-safe, UI-independent entry point for diagnosis inference."""

    def __init__(self, bundle: ModelBundle, model: ClassificationModel, device: torch.device) -> None:
        self.bundle = bundle
        self._model = model
        self.device = device

    @classmethod
    def from_bundle(cls, path: Pathish, *, device: str = "auto") -> "DiagnosisEngine":
        bundle = ModelBundle.load(path)
        resolved_device = _resolve_device(device)
        model = ClassificationModel(
            input_size=len(FEATURE_NAMES), num_classes=len(bundle.classes)
        )
        try:
            state = torch.load(bundle.weights_path, map_location=resolved_device, weights_only=True)
            model.load_state_dict(state, strict=True)
        except Exception as exc:
            raise ArtifactCompatibilityError(f"无法加载模型权重：{exc}") from exc
        model.to(resolved_device)
        model.eval()
        return cls(bundle=bundle, model=model, device=resolved_device)

    def diagnose(self, signal: Signal | Sequence[float]) -> DiagnosisResult:
        if not isinstance(signal, Signal):
            signal = Signal(signal)
        if signal.sampling_rate_hz != self.bundle.sampling_rate_hz:
            raise InvalidSignalError(
                f"模型要求 {self.bundle.sampling_rate_hz} Hz 采样率，"
                f"收到 {signal.sampling_rate_hz} Hz"
            )
        features = extract_feature_vector(
            signal.samples,
            sampling_rate_hz=signal.sampling_rate_hz,
            min_samples=self.bundle.min_samples,
        )
        if not np.all(np.isfinite(features)):
            raise DiagnosisError("特征提取结果必须全部是有限数值")
        mean = self.bundle.scaler_mean.astype(np.float32)
        scale = self.bundle.scaler_scale.astype(np.float32)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            normalized = ((features - mean) / scale).astype(np.float32)
        if not np.all(np.isfinite(normalized)):
            raise DiagnosisError("标准化后的模型输入必须全部是有限数值")
        tensor = torch.from_numpy(normalized).unsqueeze(0).to(self.device)
        try:
            with torch.inference_mode():
                logits = self._model(tensor)
                if logits.shape != (1, len(self.bundle.classes)):
                    raise DiagnosisError(
                        "模型 logits 形状与 bundle 类别数量不一致"
                    )
                if not bool(torch.isfinite(logits).all().item()):
                    raise DiagnosisError("模型 logits 必须全部是有限数值")
                probability_tensor = torch.softmax(logits, dim=1)
                if not bool(torch.isfinite(probability_tensor).all().item()):
                    raise DiagnosisError("模型概率必须全部是有限数值")
                probabilities = probability_tensor[0].cpu().numpy()
        except DiagnosisError:
            raise
        except Exception as exc:
            raise DiagnosisError(f"模型推理失败：{exc}") from exc
        class_id = int(np.argmax(probabilities))
        class_definition = self.bundle.classes[class_id]
        confidence = float(probabilities[class_id])
        warnings: tuple[str, ...] = ()
        if confidence < self.bundle.confidence_warning_threshold:
            warnings = ("模型置信度较低，请结合波形、PRPD 和人工经验复核。",)
        return DiagnosisResult(
            class_id=class_definition.id,
            label=class_definition.name,
            confidence=confidence,
            probabilities={
                definition.name: float(probabilities[index])
                for index, definition in enumerate(self.bundle.classes)
            },
            features=feature_mapping(features),
            model_version=self.bundle.model_version,
            source_id=signal.source_id,
            warnings=warnings,
        )

    def diagnose_file(self, path: Pathish) -> DiagnosisResult:
        source = Path(path)
        return self.diagnose(
            Signal(
                read_txt_signal(source),
                sampling_rate_hz=self.bundle.sampling_rate_hz,
                source_id=str(source.resolve()),
            )
        )

    def diagnose_files(
        self,
        paths: Iterable[Pathish],
        *,
        continue_on_error: bool = True,
    ) -> BatchDiagnosisResult:
        items: list[BatchDiagnosisItem] = []
        for path in paths:
            source = str(path)
            try:
                items.append(BatchDiagnosisItem(source=source, result=self.diagnose_file(path)))
            except DiagnosisError as exc:
                items.append(BatchDiagnosisItem(source=source, error=str(exc)))
                if not continue_on_error:
                    break
        return BatchDiagnosisResult(tuple(items))


def _resolve_device(requested: str) -> torch.device:
    normalized = requested.lower()
    if normalized == "auto":
        normalized = "cuda" if torch.cuda.is_available() else "cpu"
    if normalized.startswith("cuda") and not torch.cuda.is_available():
        raise ArtifactCompatibilityError("请求了 CUDA，但当前环境不可用")
    try:
        return torch.device(normalized)
    except (RuntimeError, ValueError) as exc:
        raise ArtifactCompatibilityError(f"无效的推理设备：{requested}") from exc
