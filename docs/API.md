# Python SDK 接口

`pd_diagnosis` 顶层只导出稳定诊断接口。导入 SDK 不会加载 PySide6、Matplotlib、Pandas 或训练模块；桌面依赖只在启动 GUI 时延迟导入。

## 安装与创建引擎

仅使用 SDK：

```powershell
python -m pip install partial-discharge-diagnosis
```

开发桌面应用：

```powershell
conda create -n pd-diagnosis python=3.10 -y
conda activate pd-diagnosis
python -m pip install --upgrade pip
python -m pip install -e ".[gui,dev]"
```

不要把开发依赖安装到 Conda `base`，也不要同时激活 Conda 环境和 `.venv`。Conda 负责隔离 Python 环境，`python -m pip` 负责把当前源码及可选依赖安装进已经激活的 `pd-diagnosis` 环境。需要训练功能时改用 `python -m pip install -e ".[gui,train,dev]"`。

```python
from pd_diagnosis import DiagnosisEngine

engine = DiagnosisEngine.from_bundle("models/default", device="auto")
```

`device` 支持 `auto`、`cpu`、`cuda` 或具体 CUDA 设备。请求不可用 CUDA 会抛出 `ArtifactCompatibilityError`，不会静默回退。模型输入维度来自 SDK 特征契约，类别数量、采样率、最少采样点和低置信度阈值来自 bundle。

桌面程序寻找默认模型的顺序为：`PD_DIAGNOSIS_MODEL` 环境变量、当前仓库 `models/default`、安装包共享数据目录。外部 SDK 调用建议显式传入 bundle 路径。

## 数组诊断

```python
from pd_diagnosis import Signal

result = engine.diagnose(
    Signal(
        samples=my_samples,
        sampling_rate_hz=1_000_000,
        source_id="sensor-01/2026-08-10",
    )
)
```

也可直接传一维数值序列，此时使用 `Signal` 的默认采样率。SDK 会复制输入为独立的 `float32` 快照，验证维度、长度和有限数值，并在特征、标准化输入、logits、概率四个边界拒绝 NaN 或无穷值。

`DiagnosisResult` 包含：

- `class_id`、`label`、`confidence`；
- 按模型类别顺序保存的 `probabilities`；
- 十项 `legacy-v1` 特征组成的 `features`；
- `model_version`、`source_id`、`run_id`、UTC `created_at`；
- `warnings`，例如低置信度复核提示或历史记录保存失败提示。

## 文件和批量诊断

```python
result = engine.diagnose_file("signal.txt")
batch = engine.diagnose_files(["a.txt", "b.txt"], continue_on_error=True)
```

正式文件接口只接受 UTF-8、带 UTF-8 BOM 或 ASCII 的空白符分隔 TXT。读取权限错误、解码错误和非法 token 都转换为 `InvalidSignalError`；token 错误包含行号和位置。

每个 `BatchDiagnosisItem` 在构造时强制满足：`result` 与 `error` 必须且只能提供一个。单文件失败不会伪造概率，也不会丢弃其他文件结果。

## 异常

- `InvalidSignalError`：文件、格式、维度、长度、采样率或数值不满足输入契约；
- `ArtifactCompatibilityError`：模型清单、路径、哈希、架构、特征、类别、scaler、权重或设备不兼容；
- `DiagnosisError`：其余可预期推理失败的共同父类；
- `PersistenceWarning`：推理成功但历史记录未能写入时使用的警告类别，文本会附加到结果 `warnings`。

## 持久化应用服务

纯 SDK 不自动写磁盘。需要历史记录时显式组合：

```python
from pd_diagnosis.service import DiagnosisService
from pd_diagnosis.storage import HistoryRepository

history = HistoryRepository("diagnosis.sqlite3")
service = DiagnosisService(engine, history)
result = service.diagnose_file("signal.txt")
```

推理成功而 SQLite 写入失败时，Service 仍返回诊断结果，并追加持久化警告。推理失败且错误记录也写入失败时，调用者收到的仍是原始 `DiagnosisError`。完整数据库异常写入应用滚动日志。

历史仓库支持带查询条件的 `list(limit, offset, query)` 与 `count(query)`。相同 `run_id` 使用 SQLite UPSERT 更新，不会以 `INSERT OR REPLACE` 的删除语义替换原记录。

训练入口位于 `pd_diagnosis.experimental.training`，不属于稳定 API。
