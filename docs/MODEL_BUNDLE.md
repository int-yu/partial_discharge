# 模型 Bundle 格式

每个模型目录必须包含：

- `manifest.json`：版本、架构、输入契约、类别和工件 SHA-256；
- `weights.pth`：仅包含与指定架构匹配的 Torch `state_dict`；
- `scaler.npz`：标准化器 `mean`、`scale` 数组，读取时始终设置 `allow_pickle=False`。

## schema_version 1 清单

| 字段 | 约束 |
|---|---|
| `schema_version` | 整数，当前必须为 `1` |
| `model_version` | 非空字符串 |
| `architecture` | 当前必须为 `classification-mlp-v1` |
| `feature_schema` | 当前必须与 SDK 的 `legacy-v1` 一致 |
| `feature_names` | 必须与 SDK 十项特征名称、顺序完全一致 |
| `sampling_rate_hz` | 大于 0 的整数 |
| `min_samples` | 大于 0 的整数 |
| `confidence_warning_threshold` | 可选，`0.0..1.0`；schema 1 缺省为 `0.6` |
| `classes` | 非空；ID 从 0 连续；名称非空且不重复 |
| `weights_file` / `scaler_file` | 非空相对路径，解析后必须仍位于 bundle 目录内 |
| `weights_sha256` / `scaler_sha256` | 必填的 64 位 SHA-256 十六进制字符串 |

加载器会先解析并验证清单类型，再解析受约束的工件路径与哈希。绝对路径、`..` 目录逃逸以及解析到 bundle 外部的符号链接都会被拒绝。权重始终使用 `torch.load(..., weights_only=True)` 加载。

`scaler.npz` 中 `mean` 和 `scale` 必须都是与特征数量相同的一维有限数组，且所有 `scale` 严格大于 0。加载权重时网络结构、键名和张量形状必须严格匹配。

## 创建和迁移

训练与迁移写入器共用 `artifacts.sha256_file`，避免不同模块产生不同哈希实现。旧版 sklearn `scaler.pkl` 只能显式迁移：

```powershell
pd-migrate-model legacy/best_model.pth legacy/scaler.pkl output/model --trusted
```

`--trusted` 表示调用者确认 pickle 来自可信来源；日常 SDK 推理永远不会加载 pickle。

特征公式、单位、顺序或采样假设发生变化时，必须创建新的 `feature_schema` 并重新训练，不能覆盖 `legacy-v1` 含义。保留旧 bundle 和 `model_version`，才能复现历史诊断。

## 安装位置

构建产物把默认三件套安装到 Python 数据目录：

```text
share/partial-discharge-diagnosis/models/default/
```

桌面启动器优先使用环境变量和仓库本地模型，二者都不存在时才使用该安装位置。wheel 验证必须同时检查三件套与 `pd_diagnosis/py.typed`。
