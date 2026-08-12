# Python SDK 接口

`pd_diagnosis` 顶层只导出稳定的诊断接口。Qt、Matplotlib、Pandas 和训练依赖不会因导入 SDK 而加载。

## 创建引擎

```python
from pd_diagnosis import DiagnosisEngine

engine = DiagnosisEngine.from_bundle("models/default", device="auto")
```

`device` 支持 `auto`、`cpu`、`cuda` 或具体 CUDA 设备。请求不可用的 CUDA 会抛出 `ArtifactCompatibilityError`，不会静默回退。

## 数组诊断

```python
from pd_diagnosis import Signal

result = engine.diagnose(
    Signal(
        samples=[...],
        sampling_rate_hz=1_000_000,
        source_id="sensor-01/2026-08-09",
    )
)
```

`DiagnosisResult` 包含：

- `class_id`、`label`、`confidence`
- `probabilities`：按模型类别顺序排列的名称到概率映射
- `features`：十项 `legacy-v1` 特征
- `model_version`、`source_id`、`run_id`、`created_at`
- `warnings`：例如低置信度复核提示

## 文件和批量诊断

```python
result = engine.diagnose_file("signal.txt")
batch = engine.diagnose_files(["a.txt", "b.txt"], continue_on_error=True)
```

TXT 支持逐行或空白符分隔数值。非法 token 会报告行号和位置。批量结果的每个 `BatchDiagnosisItem` 都包含 `result` 或 `error`，单文件失败不会伪造诊断概率。

## 异常

- `InvalidSignalError`：格式、维度、长度、采样率或数值非法
- `ArtifactCompatibilityError`：模型清单、校验值、特征版本或设备不兼容
- `DiagnosisError`：其余推理错误

## 持久化应用服务

纯 SDK 不自动写磁盘。需要历史记录时显式组合：

```python
from pd_diagnosis.service import DiagnosisService
from pd_diagnosis.storage import HistoryRepository

history = HistoryRepository("diagnosis.sqlite3")
service = DiagnosisService(engine, history)
result = service.diagnose_file("signal.txt")
```

训练位于 `pd_diagnosis.experimental.training`，不属于稳定 API。
