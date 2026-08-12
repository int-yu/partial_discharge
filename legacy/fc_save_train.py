import os
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset
from sklearn.metrics import classification_report, confusion_matrix


# 自定义数据集类
class FeatureDataset(Dataset):
    def __init__(self, features, labels):
        self.features = features
        self.labels = labels

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        feature = self.features[idx]
        label = self.labels[idx]
        return torch.tensor(feature, dtype=torch.float32), torch.tensor(label, dtype=torch.long)


def extract_features(signal):
    """
    从一维时序信号中提取10种特征
    返回: 包含10个特征值的numpy数组
    """
    sampling_rate = 1e6
    # 转换为numpy数组进行计算
    signal_np = np.array(signal, dtype=np.float32)
    n = len(signal_np)

    # 1. 最大值 (mV)
    max_value = np.max(signal_np) * 1000  # 转换为mV

    # 2. 峰峰值 (mV)
    peak_to_peak = (np.max(signal_np) - np.min(signal_np)) * 1000

    # 3. 脉冲均值 (V)
    pulse_mean = np.mean(signal_np)

    # 4. 脉冲方差
    pulse_variance = np.var(signal_np)

    # 初始化频谱特征为0
    spectral_master_freq = 0.0
    spectral_master_peak = 0.0
    spectral_mean = 0.0
    spectral_variance = 0.0

    # 5-8. 频谱特征 (需要FFT计算)
    if n > 1:  # 确保信号长度足够进行FFT
        fft_result = np.fft.fft(signal_np)
        fft_mag = np.abs(fft_result) / n  # 归一化幅度
        freqs = np.fft.fftfreq(n, 1 / sampling_rate)

        # 仅考虑正频率
        positive_mask = freqs > 0
        positive_freqs = freqs[positive_mask]
        positive_mag = fft_mag[positive_mask]

        if len(positive_mag) > 0:  # 确保有正频率分量
            # 5. 频谱主频率 (Hz)
            dominant_freq_idx = np.argmax(positive_mag)
            spectral_master_freq = positive_freqs[dominant_freq_idx]

            # 6. 频谱主频率峰值 (V)
            spectral_master_peak = positive_mag[dominant_freq_idx]

            # 7. 频谱均值 (V)
            spectral_mean = np.mean(positive_mag)

            # 8. 频谱方差
            spectral_variance = np.var(positive_mag)

    # 9. 峰度 (衡量分布尖锐度)
    if n > 3:  # 峰度需要至少4个点才有意义
        kurtosis = np.mean((signal_np - np.mean(signal_np)) ** 4) / (np.std(signal_np) ** 4 + 1e-10) - 3
    else:
        kurtosis = 0.0

    # 10. 偏度 (衡量分布不对称性)
    if n > 1:  # 偏度需要至少2个点
        skewness = np.mean((signal_np - np.mean(signal_np)) ** 3) / (np.std(signal_np) ** 3 + 1e-10)
    else:
        skewness = 0.0

    return np.array([
        max_value,
        peak_to_peak,
        pulse_mean,
        pulse_variance,
        spectral_master_freq,
        spectral_master_peak,
        spectral_mean,
        spectral_variance,
        kurtosis,
        skewness
    ], dtype=np.float32)


# 修正后的数据加载函数
def load_data(data_dir):
    features = []
    labels = []

    # 遍历每个类别文件夹
    for class_dir in sorted(os.listdir(data_dir)):
        class_path = os.path.join(data_dir, class_dir)

        if not os.path.isdir(class_path):
            continue

        class_label = int(class_dir)

        # 遍历类别文件夹中的每个文件
        for file_name in os.listdir(class_path):
            file_path = os.path.join(class_path, file_name)

            try:
                with open(file_path, 'r') as f:
                    # 读取文件内容
                    lines = f.readlines()
                    data = []

                    # 处理单行或多行数据
                    if len(lines) == 1:
                        # 单行数据，用空格分隔
                        values = lines[0].strip().split()
                        if values:
                            data = [float(value) for value in values]
                    else:
                        # 多行数据，每行一个值
                        for line in lines:
                            value = line.strip()
                            if value:  # 跳过空行
                                try:
                                    data.append(float(value))
                                except ValueError:
                                    # 如果转换失败，跳过该行
                                    continue

                    # 确保有足够的数据点
                    if len(data) > 10:  # 需要足够的数据点来提取特征
                        # 提取特征
                        feature_vector = extract_features(data)
                        features.append(feature_vector)
                        labels.append(class_label)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    # 转换为numpy数组
    features = np.array(features)
    labels = np.array(labels)
    return features, labels


# 定义神经网络模型
class ClassificationModel(nn.Module):
    def __init__(self, input_size, num_classes):
        super(ClassificationModel, self).__init__()
        self.fc1 = nn.Linear(input_size, 128)
        self.bn1 = nn.BatchNorm1d(128)
        self.dropout1 = nn.Dropout(0.3)

        self.fc2 = nn.Linear(128, 64)
        self.bn2 = nn.BatchNorm1d(64)
        self.dropout2 = nn.Dropout(0.3)

        self.fc3 = nn.Linear(64, 32)
        self.bn3 = nn.BatchNorm1d(32)

        self.fc4 = nn.Linear(32, 16)
        self.bn4 = nn.BatchNorm1d(16)

        self.fc5 = nn.Linear(16, num_classes)

    def forward(self, x):
        x = torch.relu(self.bn1(self.fc1(x)))
        x = self.dropout1(x)

        x = torch.relu(self.bn2(self.fc2(x)))
        x = self.dropout2(x)

        x = torch.relu(self.bn3(self.fc3(x)))

        x = torch.relu(self.bn4(self.fc4(x)))

        x = self.fc5(x)
        return x


# 训练函数
def train_model(model, train_loader, val_loader, criterion, optimizer, device, num_epochs=100, patience=10,pth=""):
    best_val_loss = float('inf')
    patience_counter = 0

    for epoch in range(num_epochs):
        # 训练阶段
        model.train()
        train_loss = 0.0
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)

            # 前向传播
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            # 反向传播和优化
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * inputs.size(0)

        # 验证阶段
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * inputs.size(0)

        # 计算平均损失
        train_loss = train_loss / len(train_loader.dataset)
        val_loss = val_loss / len(val_loader.dataset)

        print(f'Epoch {epoch + 1}/{num_epochs} - Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}')

        # 早停机制
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), pth)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f'Early stopping at epoch {epoch + 1}')
                break

    # 加载最佳模型
    model.load_state_dict(torch.load(pth))
    return model


# 评估函数
def evaluate_model(model, test_loader, device):
    model.eval()
    all_labels = []
    all_preds = []
    test_loss = 0.0
    criterion = nn.CrossEntropyLoss()

    with torch.no_grad():
        for inputs, labels in test_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            test_loss += loss.item() * inputs.size(0)

            _, preds = torch.max(outputs, 1)
            all_labels.extend(labels.cpu().numpy())
            all_preds.extend(preds.cpu().numpy())

    test_loss = test_loss / len(test_loader.dataset)

    # 计算准确率
    accuracy = np.sum(np.array(all_preds) == np.array(all_labels)) / len(all_labels)

    print(f'Test Loss: {test_loss:.4f}, Test Accuracy: {accuracy:.4f}')
    print("\nClassification Report:")
    print(classification_report(all_labels, all_preds, target_names=['Class 0', 'Class 1', 'Class 2', 'Class 3']))
    print("\nConfusion Matrix:")
    print(confusion_matrix(all_labels, all_preds))

    return test_loss, accuracy


