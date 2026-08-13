# 局部放电类型智能诊断

本项目提供可复用的 Python SDK 和基于 PySide6 的 Windows 桌面应用，用于对一维局部放电信号进行特征提取、类型诊断、批量处理和历史追溯。

当前模型识别四类缺陷：

- 金属突出物缺陷
- 自由微粒缺陷
- 绝缘子表面金属污染物缺陷
- 气隙缺陷

## 安装

推荐为本项目创建独立的 Conda 环境。不要安装到 `base` 环境，也不要同时激活 Conda 环境和 `.venv`：

```powershell
conda create -n pd-diagnosis python=3.10 -y
conda activate pd-diagnosis
python -m pip install --upgrade pip
python -m pip install -e ".[gui,dev]"
```

Conda 负责创建和隔离 Python 环境；pip 只把当前项目及依赖安装进已经激活的 Conda 环境，因此不会污染 `base`。请使用 `python -m pip`，确保调用的是当前环境里的 pip。

如果还需要训练模型，再安装训练依赖：

```powershell
python -m pip install -e ".[gui,train,dev]"
```

PyTorch 的 CPU/CUDA 构建与硬件和驱动有关；需要指定 CUDA 版本时，请先在已激活的 `pd-diagnosis` 环境中按 PyTorch 官方说明安装对应构建，再执行项目安装命令。

## Python SDK

```python
from pd_diagnosis import DiagnosisEngine

engine = DiagnosisEngine.from_bundle("models/default")
result = engine.diagnose_file("data/test/金属突出物缺陷/a1.txt")

print(result.label)
print(result.confidence)
print(result.probabilities)
```

数组输入使用 `Signal` 明确传递采样率：

```python
from pd_diagnosis import Signal

result = engine.diagnose(
    Signal(samples=my_samples, sampling_rate_hz=1_000_000, source_id="sensor-01")
)
```

当前 `legacy-v1` 模型要求 1 MHz 采样率和至少 100 个有限数值采样点。正式文件接口仅支持空白符分隔的 TXT。

## 桌面应用

```powershell
conda activate pd-diagnosis
python -m pd_diagnosis
```

也可以使用安装时注册的 `pd-diagnosis` 命令启动。

默认模型按以下优先级解析：

1. 环境变量 `PD_DIAGNOSIS_MODEL` 指定的 bundle；
2. 当前仓库的 `models/default`；
3. 随 Python 包安装到共享数据目录的默认模型。

运行日志默认写入平台用户数据目录下的 `logs/application.log`，采用滚动文件，便于排查启动、推理、持久化和后台任务错误。

## 开发检查

```powershell
ruff check .
mypy src/pd_diagnosis
pytest --cov=pd_diagnosis --cov-report=term-missing
```

GUI 测试使用无窗口平台插件；本地自动化环境可设置 `QT_QPA_PLATFORM=offscreen` 和 `MPLBACKEND=QtAgg`。

## 旧模型迁移

旧版 `best_model.pth + scaler.pkl` 需要先转换为带清单和校验值的模型 bundle：

```powershell
pd-migrate-model legacy/best_model.pth legacy/scaler.pkl models/default --trusted
```

`scaler.pkl` 基于 pickle，只能迁移可信来源文件。新格式使用不可执行的 NumPy 参数文件。

## 目录

- `src/pd_diagnosis`：SDK、存储和桌面应用
- `models`：版本化模型 bundle
- `data/train`、`data/test`：训练与验证样本
- `tests`：自动化测试
- `legacy`：重构前原始实现和归档
