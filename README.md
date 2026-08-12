# 局部放电类型智能诊断

本项目提供可复用的 Python SDK 和基于 PySide6 的 Windows 桌面应用，用于对一维局部放电信号进行特征提取、类型诊断、批量处理和历史追溯。

当前模型识别四类缺陷：

- 金属突出物缺陷
- 自由微粒缺陷
- 绝缘子表面金属污染物缺陷
- 气隙缺陷

## 安装

推荐使用 Python 3.10 或 3.11。PyTorch 的 CPU/CUDA 构建请先按运行环境从官方源安装，再安装本项目：

```powershell
python -m pip install -e ".[gui,train,dev]"
```

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
pd-diagnosis
```

默认模型位于 `models/default`。也可通过环境变量 `PD_DIAGNOSIS_MODEL` 指定模型 bundle。

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
