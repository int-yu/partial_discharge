# 模型 Bundle 格式

每个模型目录包含：

- `manifest.json`：格式版本、模型版本、类别、采样率、特征顺序和 SHA-256
- `weights.pth`：仅包含 Torch `state_dict`
- `scaler.npz`：标准化器的 `mean` 和 `scale` 数组，读取时禁止 pickle

SDK 在加载时验证清单、特征顺序、文件校验值、类别 ID 和标准化参数维度。当前正式支持 `schema_version=1`、`feature_schema=legacy-v1` 和 `classification-mlp-v1`。

旧版 sklearn `scaler.pkl` 只能通过 `pd-migrate-model ... --trusted` 转换。该参数表示调用者确认 pickle 来自可信来源；SDK 的日常推理不会加载 pickle。

特征公式、单位或采样率发生变化时必须使用新的 `feature_schema` 并重新训练模型，不能覆盖 `legacy-v1` 的含义。
