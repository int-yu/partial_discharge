from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Sized, cast

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ..artifacts import sha256_file
from ..features import FEATURE_NAMES, FEATURE_SCHEMA, extract_feature_vector
from ..migration import DEFAULT_CLASSES
from ..model import ClassificationModel
from ..signal_io import read_txt_signal

ProgressCallback = Callable[[int, int, float, float], None]


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    data_dir: Path
    output_dir: Path
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    patience: int = 10
    random_state: int = 42


@dataclass(frozen=True, slots=True)
class TrainingResult:
    output_dir: Path
    best_validation_loss: float
    test_accuracy: float
    completed_epochs: int
    cancelled: bool = False


def train(
    config: TrainingConfig,
    *,
    progress: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> TrainingResult:
    """Train a legacy-v1 model. This API is intentionally experimental."""
    try:
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("训练需要安装 train 可选依赖") from exc

    features: list[np.ndarray] = []
    labels: list[int] = []
    for class_dir in sorted(config.data_dir.iterdir()):
        if not class_dir.is_dir() or not class_dir.name.isdigit():
            continue
        class_id = int(class_dir.name)
        for path in sorted(class_dir.glob("*.txt")):
            features.append(extract_feature_vector(read_txt_signal(path)))
            labels.append(class_id)
    if not features:
        raise ValueError(f"训练目录中没有有效 TXT 样本：{config.data_dir}")

    values = np.asarray(features, dtype=np.float32)
    targets = np.asarray(labels, dtype=np.int64)
    x_train, x_test, y_train, y_test = train_test_split(
        values,
        targets,
        test_size=0.2,
        random_state=config.random_state,
        stratify=targets,
    )
    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_train).astype(np.float32)
    x_test = scaler.transform(x_test).astype(np.float32)
    x_train, x_validation, y_train, y_validation = train_test_split(
        x_train,
        y_train,
        test_size=0.2,
        random_state=config.random_state,
        stratify=y_train,
    )

    def loader(x: np.ndarray, y: np.ndarray, *, shuffle: bool = False) -> DataLoader:
        dataset = TensorDataset(torch.from_numpy(x), torch.from_numpy(y))
        return DataLoader(dataset, batch_size=config.batch_size, shuffle=shuffle)

    train_loader = loader(x_train, y_train, shuffle=True)
    validation_loader = loader(x_validation, y_validation)
    test_loader = loader(x_test, y_test)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ClassificationModel(10, len(np.unique(targets))).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    stale_epochs = 0
    completed_epochs = 0

    for epoch in range(1, config.epochs + 1):
        if cancel_event is not None and cancel_event.is_set():
            break
        model.train()
        train_loss = 0.0
        for inputs, batch_labels in train_loader:
            inputs, batch_labels = inputs.to(device), batch_labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(inputs), batch_labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(inputs)
        train_loss /= len(cast(Sized, train_loader.dataset))

        model.eval()
        validation_loss = 0.0
        with torch.inference_mode():
            for inputs, batch_labels in validation_loader:
                inputs, batch_labels = inputs.to(device), batch_labels.to(device)
                validation_loss += criterion(model(inputs), batch_labels).item() * len(inputs)
        validation_loss /= len(cast(Sized, validation_loader.dataset))
        completed_epochs = epoch
        if progress is not None:
            progress(epoch, config.epochs, train_loss, validation_loss)
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= config.patience:
                break

    cancelled = cancel_event is not None and cancel_event.is_set()
    if best_state is None:
        raise RuntimeError("训练未生成有效模型")
    model.load_state_dict(best_state)
    model.to(device).eval()
    correct = total = 0
    with torch.inference_mode():
        for inputs, batch_labels in test_loader:
            predictions = model(inputs.to(device)).argmax(dim=1).cpu()
            correct += int((predictions == batch_labels).sum())
            total += len(batch_labels)

    output = config.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    weights_path = output / "weights.pth"
    scaler_path = output / "scaler.npz"
    torch.save(best_state, weights_path)
    np.savez(scaler_path, mean=scaler.mean_, scale=scaler.scale_)
    manifest = {
        "schema_version": 1,
        "model_version": f"trained-{config.random_state}-{completed_epochs}",
        "architecture": "classification-mlp-v1",
        "feature_schema": FEATURE_SCHEMA,
        "feature_names": list(FEATURE_NAMES),
        "sampling_rate_hz": 1_000_000,
        "min_samples": 100,
        "confidence_warning_threshold": 0.6,
        "classes": [{"id": index, "name": name} for index, name in enumerate(DEFAULT_CLASSES)],
        "weights_file": weights_path.name,
        "weights_sha256": sha256_file(weights_path),
        "scaler_file": scaler_path.name,
        "scaler_sha256": sha256_file(scaler_path),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return TrainingResult(
        output_dir=output,
        best_validation_loss=best_loss,
        test_accuracy=correct / total if total else 0.0,
        completed_epochs=completed_epochs,
        cancelled=cancelled,
    )
