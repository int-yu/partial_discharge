import sys
import joblib
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QFileDialog, QComboBox, QLineEdit, QStatusBar, QSplitter,
    QGroupBox, QProgressBar, QMessageBox, QTextEdit, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import torch
import pandas as pd
import os
from datetime import datetime
from copy import deepcopy
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader
from fc_save_train import FeatureDataset, ClassificationModel, train_model, evaluate_model,load_data
import json



def extract_features(signal):
    """
    从一维时序信号中提取10种特征
    返回: 包含10个特征值的torch.Tensor
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

    # 将所有特征组合成一维张量
    features = np.array([
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
    ],dtype=float)
    print(f"{features}")
    return features

def extract_features_dict(signal):
    """
    从一维时序信号中提取10种特征
    返回: 包含10个特征值的torch.Tensor
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

    # 将所有特征组合成一维张量
    features = {
        "最大值 (mV)":max_value,
        "峰峰值 (mV)":peak_to_peak,
        "脉冲均值 (V)":pulse_mean,
        "脉冲方差":pulse_variance,
        "频谱主频率 (Hz)":spectral_master_freq,
        "频谱主频率峰值 (V)":spectral_master_peak,
        "频谱均值 (V)":spectral_mean,
        "频谱方差":spectral_variance,
        "峰度 (衡量分布尖锐度)":kurtosis,
        "偏度 (衡量分布不对称性)":skewness
    }

    return features



#生成PRPD数据
def generate_prpd_data(discharge_data):
    """
    从放电数据生成PRPD数据
    """
    # 确保数据是NumPy数组
    if not isinstance(discharge_data, np.ndarray):
        discharge_data = np.array(discharge_data)

    # 确保是一维数组
    if discharge_data.ndim > 1:
        discharge_data = discharge_data.flatten()
    def generate_reference_signal(length, frequency=50, sampling_rate=1e6):
        """
        生成工频参考电压信号
        """
        t = np.arange(length) / sampling_rate
        voltage = np.sin(2 * np.pi * frequency * t)
        return voltage

    reference_voltage = generate_reference_signal(len(discharge_data))

    def detect_discharge_pulses(data, threshold=0.1):
        """
        检测放电脉冲
        """
        # 应用阈值检测
        above_threshold = np.where(data > threshold)[0]

        # 分组连续的点
        pulse_indices = []
        current_pulse = []

        for i in range(len(above_threshold)):
            if i == 0 or above_threshold[i] - above_threshold[i - 1] == 1:
                current_pulse.append(above_threshold[i])
            else:
                if current_pulse:  # 确保当前脉冲非空
                    pulse_indices.append(current_pulse)
                current_pulse = [above_threshold[i]]

        if current_pulse:
            pulse_indices.append(current_pulse)

        # 提取脉冲特征
        pulses = []
        for indices in pulse_indices:
            pulse_data = data[indices]
            max_index = indices[np.argmax(pulse_data)]
            amplitude = np.max(pulse_data)
            pulses.append({
                'indices': indices,
                'max_index': max_index,
                'amplitude': amplitude
            })

        return pulses

    def calculate_phase(pulse_index, reference_voltage):
        """
        计算放电脉冲的相位
        """
        # 找到最近的过零点
        zero_crossings = np.where(np.diff(np.sign(reference_voltage)))[0]

        # 如果找不到过零点，返回0
        if len(zero_crossings) == 0:
            return 0

        # 找到脉冲前的最后一个过零点
        prev_zero_crossings = zero_crossings[zero_crossings < pulse_index]

        # 如果脉冲前没有过零点，使用第一个过零点
        if len(prev_zero_crossings) == 0:
            prev_zero_crossing = zero_crossings[0]
        else:
            prev_zero_crossing = prev_zero_crossings[-1]

        # 计算相位
        phase = (pulse_index - prev_zero_crossing) / len(reference_voltage) * 360
        phase = phase % 360  # 确保在0-360度范围内

        return phase


    # 检测放电脉冲
    pulses = detect_discharge_pulses(discharge_data)

    # 初始化PRPD数据结构
    phase_bins = np.linspace(0, 360, 36)  # 10度一个bin
    amplitude_bins = np.linspace(0, np.max(discharge_data), 20)
    prpd = np.zeros((len(phase_bins), len(amplitude_bins)))

    # 处理每个脉冲
    for pulse in pulses:
        phase = calculate_phase(pulse['max_index'], reference_voltage)
        amplitude = pulse['amplitude']

        # 找到对应的bin
        phase_idx = np.digitize(phase, phase_bins) - 1
        amp_idx = np.digitize(amplitude, amplitude_bins) - 1

        # 确保索引在范围内
        if 0 <= phase_idx < len(phase_bins) and 0 <= amp_idx < len(amplitude_bins):
            prpd[phase_idx, amp_idx] += 1

    return phase_bins, amplitude_bins, prpd

# 读取txt文件中的数据
def date_get_num(file_path):
    data=[]
    labels=[]

    with open(file_path, 'r') as file:
        lines = file.readlines()
        if not lines:
            return data

        # 每行只有一个数值，直接读取
        for line in lines:
            value = line.strip()
            if value:  # 跳过空行
                try:
                    data.append(float(value))
                except ValueError:
                    # 如果转换失败，跳过该行
                    continue

    return data


class PDTypePredictor:
    """局部放电类型预测模型"""

    def __init__(self, model, scaler):
        self.model = model
        self.scaler = scaler  # 添加标准化器
        self.classes = ['金属突出物缺陷', '自由微粒缺陷', '绝缘子表面金属污染物缺陷', '气隙缺陷']

    def predict(self, features_data):
        """预测过程"""
        self.model.eval()
        error_log = None

        try:
            features_scaled = self.scaler.transform([features_data])

            # 3. 转换为张量
            data = torch.tensor(features_scaled, dtype=torch.float32)

            # 4. 确保维度正确 (batch_size, num_features)
            if data.dim() == 1:
                data = data.unsqueeze(0)  # 添加batch维度
            elif data.dim() > 2:
                data = data.view(data.size(0), -1)  # 展平多余维度

            # 5. 进行预测
            with torch.no_grad():
                output = self.model(data)
                probabilities = torch.softmax(output, dim=1)
                probabilities = probabilities.squeeze().numpy()
                predicted_class = self.classes[np.argmax(probabilities)]

            return predicted_class, probabilities, error_log

        except Exception as e:
            error_log = f"预测错误: {str(e)}"
            # 返回默认值
            probabilities = np.ones(4) / 4  # 均匀分布
            predicted_class = self.classes[np.argmax(probabilities)]
            return predicted_class, probabilities, error_log


class MplCanvas(FigureCanvas):
    """Matplotlib画布组件"""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        # 设置支持中文的字体
        plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
        plt.rcParams['axes.unicode_minus'] = False  # 显示负号

        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

    def plot_waveform(self, data):
        """绘制波形图"""
        self.ax.clear()
        self.ax.plot(data, 'b-')
        self.ax.set_title('局部放电波形')
        self.ax.set_xlabel('时间')
        self.ax.set_ylabel('幅值')
        self.fig.tight_layout()
        self.draw()

    def plot_prpd(self, phase_bins, amplitude_bins, prpd):
        """绘制PRPD图谱

        参数:
            phase_bins (array): 相位分箱边界
            amplitude_bins (array): 放电量分箱边界
            prpd (2D array): PRPD矩阵 (相位×放电量)
        """
        # 检查数据有效性
        if prpd.size == 0:
            self.ax.clear()
            self.ax.text(0.5, 0.5, "无PRPD数据",
                         ha='center', va='center', fontsize=12)
            self.ax.set_title('PRPD图谱')
            self.draw()
            return

        # 清除当前坐标轴
        self.ax.clear()

        # 绘制PRPD热图
        mesh = self.ax.pcolormesh(phase_bins, amplitude_bins, prpd.T,
                                  shading='auto', cmap='viridis')

        # 添加颜色条
        if not hasattr(self, 'prpd_colorbar'):
            self.prpd_colorbar = self.fig.colorbar(mesh, ax=self.ax)
            self.prpd_colorbar.set_label('放电频次')
        else:
            # 更新现有颜色条
            self.prpd_colorbar.update_normal(mesh)

        # 设置标题和标签
        self.ax.set_title('PRPD图谱')
        self.ax.set_xlabel('相位(度)')
        self.ax.set_ylabel('放电量(pC)')

        # 设置坐标轴范围
        self.ax.set_xlim(0, 360)

        # 动态设置Y轴范围
        max_amp = np.max(amplitude_bins) * 1.1  # 增加10%的余量
        self.ax.set_ylim(0, max(100, max_amp))  # 至少显示到100pC

        # 添加网格线
        self.ax.grid(True, linestyle='--', alpha=0.5)

        # 优化布局并重绘
        self.fig.tight_layout()
        self.draw()

    def plot_probabilities(self, probs, classes):
        """绘制概率分布图"""
        self.ax.clear()
        spacing_factor = 0.2
        bar_height = 0.05
        y_pos = np.arange(len(classes)) * spacing_factor
        bars = self.ax.barh(y_pos, probs, height=bar_height, align='center', color='skyblue')
        for i, bar in enumerate(bars):
            width = bar.get_width()
            self.ax.text(width + 0.02, bar.get_y() + bar.get_height() / 2,
                         f'{width:.2f}',
                         ha='left', va='center', fontsize=10)

        self.ax.set_yticks(y_pos)
        self.ax.set_yticklabels(classes, fontsize=8)
        self.ax.invert_yaxis()
        self.ax.set_xlabel('概率', fontsize=8)
        self.ax.set_title('放电类型概率分布', fontsize=8)
        self.ax.set_xlim(0, 1)
        self.ax.grid(axis='x', linestyle='--', alpha=0.5)
        self.ax.set_ylim(min(y_pos) - bar_height, max(y_pos) + bar_height)
        self.fig.set_size_inches(5, 2)
        self.fig.tight_layout()
        self.draw()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()


        self.model_path = f'best_model.pth'
        self.setWindowTitle("局部放电类型预测系统")
        self.setGeometry(100, 100, 1200, 1000)

        # 创建主部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 主布局
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        # 顶部标题
        title_label = QLabel("局部放电类型智能诊断系统")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 创建各个功能选项卡
        self.create_predict_tab()
        self.create_batch_tab()
        self.create_history_tab()
        self.create_settings_tab()
        self.create_work_log()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 初始化数据
        self.current_data = None
        self.history = []
        self.log_entries = []
        self.error_log = None
        self.log_action("系统启动")

        # 模型导入
        self.model = ClassificationModel(input_size=10, num_classes=4)
        self.model.load_state_dict(torch.load("best_model.pth"))
        self.scaler = joblib.load('scaler.pkl')
        self.load_settings()

        # model_state= self.para_state_dict(self.model,self.model_path)
        # self.model.load_state_dict(state_dict=model_state)

        self.model = PDTypePredictor(self.model, self.scaler)

    def load_settings(self):
        """从JSON文件加载系统设置"""
        settings_path = os.path.join(os.getcwd(), "system_settings.json")

        if not os.path.exists(settings_path):
            self.log_action("未找到系统设置文件，使用默认设置")
            return

        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            # 应用设置到UI
            self.data_path_edit.setText(settings.get("data_path", "D:/local_discharge_data"))
            self.model_path = settings.get("model_path", "default.pth")  # 更新模型路径
            self.model_path_edit.setText(self.model_path)  # 更新UI中的模型路径输入框
            self.file_path_edit.setText(settings.get("file_path", ""))
            self.traindata_path_edit.setText(settings.get("traindata_path", ""))

            if os.path.exists(self.model_path):
                self.model_info_label.setText(f"""
            模型信息:
            名称: {os.path.basename(self.model_path)}
            大小: {os.path.getsize(self.model_path) / 1024 / 1024:.2f} MB
            修改时间: {datetime.fromtimestamp(os.path.getmtime(self.model_path))}
            """)
            self.model_path_label.setText(f"当前模型: {self.model_path}")
            self.log_action(f"系统设置已从 {settings_path} 加载")
        except json.JSONDecodeError:
            self.log_action("系统设置文件格式错误，使用默认设置")
            QMessageBox.warning(self, "警告", "设置文件格式错误，使用默认设置")
        except Exception as e:
            self.log_action(f"加载系统设置失败: {str(e)}")
            QMessageBox.warning(self, "警告", f"加载设置失败: {str(e)}")

    def create_predict_tab(self):
        """创建单次预测选项卡"""
        tab = QWidget()
        self.tab_widget.addTab(tab, "单次预测")
        layout = QVBoxLayout(tab)

        # 数据输入区域
        input_group = QGroupBox("数据输入")
        input_layout = QHBoxLayout(input_group)
        self.input_text_edit = QTextEdit()
        self.input_text_edit.setReadOnly(True)  # 设置为只读
        self.input_text_edit.setFont(QFont("Courier New", 10))
        input_layout.addWidget(self.input_text_edit)

        # 左侧：数据控制
        control_layout = QVBoxLayout()

        self.data_source_combo = QComboBox()
        self.data_source_combo.addItems(["文件导入"])
        control_layout.addWidget(QLabel("数据来源:"))
        control_layout.addWidget(self.data_source_combo)
        self.input_source_text_edit = QTextEdit()
        self.input_source_text_edit.setReadOnly(True)  # 设置为只读
        self.input_source_text_edit.setFont(QFont("Courier New", 10))
        control_layout.addWidget(self.input_source_text_edit)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择数据文件...")
        control_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_file)
        control_layout.addWidget(browse_btn)

        load_btn = QPushButton("加载数据")
        load_btn.clicked.connect(self.load_data)
        control_layout.addWidget(load_btn)

        input_layout.addLayout(control_layout)

        # 右侧：数据可视化
        self.waveform_canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.prpd_canvas = MplCanvas(self, width=5, height=4, dpi=100)

        vis_layout = QVBoxLayout()
        vis_layout.addWidget(self.waveform_canvas)
        vis_layout.addWidget(self.prpd_canvas)

        input_layout.addLayout(vis_layout)
        layout.addWidget(input_group)

        # 预测区域
        predict_group = QGroupBox("预测分析")
        predict_layout = QHBoxLayout(predict_group)

        # 左侧：预测控制
        predict_control_layout = QVBoxLayout()

        predict_btn = QPushButton("执行预测")
        predict_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        predict_btn.clicked.connect(self.run_prediction)
        predict_control_layout.addWidget(predict_btn)

        self.result_label = QLabel("预测结果: 未执行")
        self.result_label.setFont(QFont("Arial", 14, QFont.Bold))
        predict_control_layout.addWidget(self.result_label)

        self.confidence_label = QLabel("置信度: -")
        predict_control_layout.addWidget(self.confidence_label)

        predict_layout.addLayout(predict_control_layout)

        # 右侧：结果可视化
        self.prob_canvas = MplCanvas(self, width=4, height=4, dpi=100)
        predict_layout.addWidget(self.prob_canvas)

        layout.addWidget(predict_group)

    def create_batch_tab(self):
        """创建批量预测选项卡"""
        tab = QWidget()
        self.tab_widget.addTab(tab, "批量预测")
        layout = QVBoxLayout(tab)

        # 批量处理区域
        batch_group = QGroupBox("批量预测")
        batch_layout = QVBoxLayout(batch_group)

        # 文件选择区域
        file_layout = QHBoxLayout()
        self.batch_file_edit = QLineEdit()
        self.batch_file_edit.setPlaceholderText("选择数据文件或文件夹...")
        file_layout.addWidget(self.batch_file_edit)

        batch_browse_btn = QPushButton("浏览...")
        batch_browse_btn.clicked.connect(self.browse_batch_file)
        file_layout.addWidget(batch_browse_btn)

        batch_layout.addLayout(file_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        batch_layout.addWidget(self.progress_bar)

        # 操作按钮
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("开始预测")
        start_btn.setStyleSheet("background-color: #2196F3; color: white;")
        start_btn.clicked.connect(self.run_batch_prediction)
        btn_layout.addWidget(start_btn)

        export_btn = QPushButton("导出结果")
        export_btn.setStyleSheet("background-color: #FF9800; color: white;")
        export_btn.clicked.connect(self.export_results)
        btn_layout.addWidget(export_btn)

        batch_layout.addLayout(btn_layout)

        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(7)
        self.result_table.setHorizontalHeaderLabels(
            ["文件名", "预测类型", "置信度", "金属突出物", "自由微粒", "绝缘子表面", "气隙缺陷"])
        self.result_table.setSortingEnabled(True)
        batch_layout.addWidget(self.result_table)

        layout.addWidget(batch_group)

    def create_history_tab(self):
        """创建历史记录选项卡"""
        tab = QWidget()
        self.tab_widget.addTab(tab, "历史记录")
        layout = QVBoxLayout(tab)

        # 历史记录区域
        history_group = QGroupBox("历史预测记录")
        history_layout = QVBoxLayout(history_group)

        # 搜索区域
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入文件名或预测类型...")
        search_layout.addWidget(self.search_edit)

        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self.search_history)
        search_layout.addWidget(search_btn)

        history_layout.addLayout(search_layout)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["时间", "数据来源", "文件名", "预测类型", "置信度", "操作"])
        history_layout.addWidget(self.history_table)

        # 操作按钮
        btn_layout = QHBoxLayout()
        view_btn = QPushButton("查看详情")
        view_btn.clicked.connect(self.view_history_detail)
        report_btn = QPushButton("生成报告")
        report_btn.clicked.connect(self.generate_report)
        delete_btn = QPushButton("删除记录")
        delete_btn.clicked.connect(self.delete_history)
        btn_layout.addWidget(view_btn)
        btn_layout.addWidget(report_btn)
        btn_layout.addWidget(delete_btn)

        history_layout.addLayout(btn_layout)

        layout.addWidget(history_group)

    def create_settings_tab(self):
        """创建系统设置选项卡"""
        tab = QWidget()
        self.tab_widget.addTab(tab, "系统设置")
        layout = QVBoxLayout(tab)

        # 模型设置
        model_group = QGroupBox("模型设置")
        model_layout = QVBoxLayout(model_group)
        self.model_path_label=QLabel()
        self.model_path_label.setText(f"当前模型: {self.model_path}")
        self.model_info_label=QLabel()
        self.model_info_label.setText("NONE")
        if os.path.exists(self.model_path):
            self.model_info_label.setText(f"""
        模型信息:
        名称: {os.path.basename(self.model_path)}
        大小: {os.path.getsize(self.model_path)/1024/1024:.2f} MB
        修改时间: {datetime.fromtimestamp(os.path.getmtime(self.model_path))}
        """)
        model_layout.addWidget(self.model_path_label)
        model_layout.addWidget(self.model_info_label)

        # 添加模型路径输入框
        model_layout.addWidget(QLabel("模型路径:"))
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setPlaceholderText("输入模型文件路径...")
        browse_model_btn = QPushButton("浏览...")
        browse_model_btn.clicked.connect(self.browse_model_path)
        model_layout.addWidget(browse_model_btn)

        model_layout.addWidget(self.model_path_edit)
        model_btn_layout = QHBoxLayout()
        load_model_btn = QPushButton("加载模型")
        load_model_btn.clicked.connect(self.load_model)
        evaluate_model_btn = QPushButton("评估模型")
        evaluate_model_btn.clicked.connect(self.evaluate_model)
        model_btn_layout.addWidget(load_model_btn)
        model_btn_layout.addWidget(evaluate_model_btn)

        model_layout.addLayout(model_btn_layout)
        layout.addWidget(model_group)

        # 系统设置
        system_group = QGroupBox("系统设置")
        system_layout = QVBoxLayout(system_group)

        system_layout.addWidget(QLabel("数据存储路径:"))
        self.data_path_edit = QLineEdit()
        self.data_path_edit.setText("D:/local_discharge_data")
        system_layout.addWidget(self.data_path_edit)

        browse_data_path_btn = QPushButton("浏览...")
        browse_data_path_btn.clicked.connect(self.browse_data_path)
        system_layout.addWidget(browse_data_path_btn)

        system_layout.addWidget(QLabel("训练路径"))
        self.traindata_path_edit = QLineEdit()
        self.traindata_path_edit.setText("D:/local_discharge_data")
        system_layout.addWidget(self.traindata_path_edit)

        browse_traindata_path_btn = QPushButton("浏览...")
        train_btn = QPushButton("训练")
        browse_traindata_path_btn.clicked.connect(self.browse_traindata_path)
        train_btn.clicked.connect(self.train_start)
        system_layout.addWidget(browse_traindata_path_btn)
        system_layout.addWidget(train_btn)

        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self.save_settings)
        system_layout.addWidget(save_btn)

        layout.addWidget(system_group)

    def create_work_log(self):
        """创建工作日志选项卡"""
        tab = QWidget()
        self.tab_widget.addTab(tab, "工作日志")
        layout = QVBoxLayout(tab)

        # 日志显示区域
        log_group = QGroupBox("系统操作日志")
        log_layout = QVBoxLayout(log_group)

        # 日志文本框
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)  # 设置为只读
        self.log_text_edit.setFont(QFont("Courier New", 10))
        log_layout.addWidget(self.log_text_edit)

        # 清空日志按钮
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.clear_log)
        btn_layout.addWidget(clear_btn)

        export_log_btn = QPushButton("导出日志")
        export_log_btn.clicked.connect(self.export_log)
        btn_layout.addWidget(export_log_btn)

        log_layout.addLayout(btn_layout)
        layout.addWidget(log_group)

    def data_show(self):
        """记录数据"""
        features_list = extract_features(self.current_data)
        # 特征名称列表
        features_names = [
            '1. 最大值 (mV)',
            '2. 峰峰值 (mV)',
            '3. 脉冲均值 (V)',
            '4. 脉冲方差',
            '5. 频谱主频率 (Hz)',
            '6. 频谱主频率峰值 (V)',
            '7. 频谱均值 (V)',
            '8. 频谱方差',
            '9. 峰度 (衡量分布尖锐度)',
            '10. 偏度 (衡量分布不对称性)'
        ]

        # 遍历特征名称和对应的值
        for feature_name, feature_value in zip(features_names, features_list):
            # 更新日志显示
            self.input_text_edit.append(f"{feature_name}: {feature_value:.4f}")  # 格式化显示为4位小数

            # 自动滚动到底部
            self.input_text_edit.verticalScrollBar().setValue(
                self.input_text_edit.verticalScrollBar().maximum()
            )
        self.log_action(f"{features_names}\n{features_list}")



    def log_action(self, action):
        """记录操作到工作日志"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{current_time}] {action}"

        # 添加到日志列表
        self.log_entries.append(log_entry)

        # 更新日志显示
        self.log_text_edit.append(log_entry)

        # 自动滚动到底部
        self.log_text_edit.verticalScrollBar().setValue(
            self.log_text_edit.verticalScrollBar().maximum()
        )

    def clear_log(self):
        """清空工作日志"""
        self.log_entries = []
        self.log_text_edit.clear()
        self.log_action("工作日志已清空")

    def export_log(self):
        """导出日志到文件"""
        file_path= self.data_path_edit.text()
        if file_path:
            try:
                with open(f"{file_path}\\work_log.txt", 'w') as f:
                    for entry in self.log_entries:
                        f.write(entry + "\n")
                self.log_action(f"日志已导出到: {file_path}")
                QMessageBox.information(self, "成功", "日志导出成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出日志失败: {str(e)}")
                self.log_action(f"导出日志失败: {str(e)}")

    def browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择数据文件", "", "数据文件 (*.csv *.txt *.mat *.npy)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
            self.input_source_text_edit.setText(f"文件路径: {file_path}")
        self.log_action(f"浏览文件：{file_path}")

    def browse_batch_file(self):
        """浏览批量文件或文件夹"""
        # 使用 getExistingDirectory 允许选择文件夹
        path = QFileDialog.getExistingDirectory(self, "选择数据文件夹")
        if path:
            self.batch_file_edit.setText(path)
        self.log_action(f"浏览文件夹：{path}")

    def browse_data_path(self):
        """浏览数据存储路径"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择数据存储路径")
        if dir_path:
            self.data_path_edit.setText(dir_path)
        self.log_action(f"浏览数据存储路径：{dir_path}")

    def browse_model_path(self):
        """浏览模型路径"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择模型文件", "", "模型文件 (*.pth *.pt)"
        )
        if file_path:
            self.model_path_edit.setText(file_path)
        self.log_action(f"浏览模型路径：{file_path}")

    def load_data(self):
        """加载数据"""
        source = self.data_source_combo.currentText()

        if source == "文件导入":
            self.current_data = None
            file_path = self.file_path_edit.text()
            if not file_path:
                QMessageBox.warning(self, "警告", "请先选择数据文件")
                self.log_action("警告请先选择数据文件")
                return

            self.log_action(f"文件地址载入{file_path}")

            # 模拟数据加载
            self.current_data = date_get_num(file_path)
            if not self.current_data or len(self.current_data) < 100:
                QMessageBox.warning(self, "警告", "数据无效或太短")
                self.log_action("警告: 数据无效或太短")
                return
            self.log_action(f"已加载数据: {file_path}")
            self.status_bar.showMessage(f"已加载数据: {file_path}")
            self.data_show()

            # 更新可视化
            self.waveform_canvas.plot_waveform(self.current_data)
            data_prpd = generate_prpd_data(self.current_data)
            self.prpd_canvas.plot_prpd(data_prpd[0], data_prpd[1], data_prpd[2])


    def run_prediction(self):
        """执行预测"""
        if self.current_data is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return

        # 执行预测
        predicted_class, probabilities, self.error_log = self.model.predict(extract_features(self.current_data))

        if self.error_log != None:
            self.log_action(self.error_log)
            self.error_log = None
            return
        # 显示结果
        self.result_label.setText(f"预测结果: {predicted_class}")
        confidence = np.max(probabilities) * 100
        self.confidence_label.setText(f"置信度: {confidence:.2f}%")

        # 更新概率分布图
        self.prob_canvas.plot_probabilities(probabilities, self.model.classes)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 添加到历史记录
        self.history.append({
            "time": current_time,
            "source": self.data_source_combo.currentText(),
            "file": self.file_path_edit.text(),
            "prediction": predicted_class,
            "confidence": confidence,
            "probabilities": probabilities
        })

        self.status_bar.showMessage("预测完成")
        self.log_action(f"预测完成: {predicted_class} (置信度: {confidence:.2f}%)")

    def run_batch_prediction(self):
        """执行批量预测"""
        # 确保UI响应
        QApplication.setOverrideCursor(Qt.WaitCursor)
        path = self.batch_file_edit.text()
        if not path:
            QMessageBox.warning(self, "警告", "请先选择数据文件或文件夹")
            return

        # 获取所有要处理的文件
        files = []
        if os.path.isdir(path):
            # 如果是文件夹，遍历所有支持的文件
            for file_name in os.listdir(path):
                if file_name.endswith(('.csv', '.txt', '.mat', '.npy')):
                    files.append(os.path.join(path, file_name))
        elif os.path.isfile(path):
            # 如果是单个文件，直接处理
            files = [path]
        else:
            QMessageBox.warning(self, "警告", "路径无效")
            return

        if not files:
            QMessageBox.warning(self, "警告", "未找到有效的数据文件")
            return

        # 设置进度条
        self.progress_bar.setRange(0, len(files))
        self.progress_bar.setValue(0)

        # 清空结果表格
        self.result_table.setRowCount(len(files))

        # 处理每个文件
        for i, file_path in enumerate(files):
            # 更新进度
            self.progress_bar.setValue(i + 1)
            self.status_bar.showMessage(f"正在处理: {os.path.basename(file_path)} ({i + 1}/{len(files)})")
            QApplication.processEvents()  # 更新UI

            try:
                # 加载数据
                data = extract_features(date_get_num(file_path))

                # 执行预测
                predicted_class, probabilities, error_log = self.model.predict(data)
                if error_log:
                    self.log_action(f"文件 {file_path} 预测错误: {error_log}")
                    # 在表格中显示错误信息
                    file_item = QTableWidgetItem(os.path.basename(file_path))
                    self.result_table.setItem(i, 0, file_item)
                    self.result_table.setItem(i, 1, QTableWidgetItem("预测错误"))
                    self.result_table.setItem(i, 2, QTableWidgetItem("-"))
                    self.result_table.setItem(i, 3, QTableWidgetItem("-"))
                    self.result_table.setItem(i, 4, QTableWidgetItem("-"))
                    self.result_table.setItem(i, 5, QTableWidgetItem("-"))
                    self.result_table.setItem(i, 6, QTableWidgetItem("-"))
                    self.status_bar.showMessage(f"批量预测失败")
                    self.log_action(f"文件预测出错")
                    return

                # 计算置信度
                confidence = np.max(probabilities) * 100

                # 添加到结果表格
                file_item = QTableWidgetItem(os.path.basename(file_path))
                self.result_table.setItem(i, 0, file_item)
                self.result_table.setItem(i, 1, QTableWidgetItem(predicted_class))
                self.result_table.setItem(i, 2, QTableWidgetItem(f"{confidence:.2f}%"))
                self.result_table.setItem(i, 3, QTableWidgetItem(f"{probabilities[0] * 100:.2f}%"))
                self.result_table.setItem(i, 4, QTableWidgetItem(f"{probabilities[1] * 100:.2f}%"))
                self.result_table.setItem(i, 5, QTableWidgetItem(f"{probabilities[2] * 100:.2f}%"))
                self.result_table.setItem(i, 6, QTableWidgetItem(f"{probabilities[3] * 100:.2f}%"))
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 添加到历史记录
                self.history.append({
                    "time": current_time,
                    "source": "batch_prediction",
                    "file": file_path,
                    "prediction": predicted_class,
                    "confidence": confidence,
                    "probabilities": probabilities
                })

            except Exception as e:
                self.log_action(f"处理文件 {file_path} 时出错: {str(e)}")
                # 在表格中显示错误信息
                file_item = QTableWidgetItem(os.path.basename(file_path))
                self.result_table.setItem(i, 0, file_item)
                self.result_table.setItem(i, 1, QTableWidgetItem("处理错误"))
                self.result_table.setItem(i, 2, QTableWidgetItem("-"))
                self.result_table.setItem(i, 3, QTableWidgetItem("-"))
                self.result_table.setItem(i, 4, QTableWidgetItem("-"))
                self.result_table.setItem(i, 5, QTableWidgetItem("-"))
                self.result_table.setItem(i, 6, QTableWidgetItem("-"))
                self.status_bar.showMessage(f"批量预测失败")
                self.log_action(f"批量预测完成失败，处理文件时出错")
                return
            finally:
                # 重置进度条
                self.progress_bar.setRange(0, 1)
                self.progress_bar.setValue(0)
                self.status_bar.showMessage("就绪")
                QApplication.restoreOverrideCursor()

        self.status_bar.showMessage(f"批量预测完成，共处理 {len(files)} 个文件")
        self.log_action(f"批量预测完成: {path}，共处理 {len(files)} 个文件")

    def export_results(self):
        """导出批量预测结果"""
        if self.result_table.rowCount() == 0:
            QMessageBox.warning(self, "警告", "没有可导出的结果")
            return

        file_path= self.data_path_edit.text()
        if file_path:
            try:
                # 创建DataFrame保存结果
                data = []
                for row in range(self.result_table.rowCount()):
                    row_data = []
                    for col in range(self.result_table.columnCount()):
                        item = self.result_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    data.append(row_data)

                headers = ["文件名", "预测类型", "置信度", "金属突出物", "自由微粒", "绝缘子表面", "气隙缺陷"]
                df = pd.DataFrame(data, columns=headers)
                df.to_csv(f"{file_path}\\batch.csv", index=False, encoding='utf_8_sig')

                self.log_action(f"结果已导出到: {file_path}")
                QMessageBox.information(self, "成功", "结果导出成功")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出结果失败: {str(e)}")
                self.log_action(f"导出结果失败: {str(e)}")

    def search_history(self):
        """搜索历史记录"""
        keyword = self.search_edit.text().strip()
        if not keyword:
            QMessageBox.information(self, "提示", "请输入搜索关键词")
            return

        # 模拟搜索
        filtered_history = [item for item in self.history if keyword in item["file"] or keyword in item["prediction"]]

        # 更新表格
        self.history_table.setRowCount(len(filtered_history))
        for i, item in enumerate(filtered_history):
            self.history_table.setItem(i, 0, QTableWidgetItem(item["time"]))
            self.history_table.setItem(i, 1, QTableWidgetItem(item["source"]))
            self.history_table.setItem(i, 2, QTableWidgetItem(item["file"]))
            self.history_table.setItem(i, 3, QTableWidgetItem(item["prediction"]))
            self.history_table.setItem(i, 4, QTableWidgetItem(f"{item['confidence']:.2f}%"))
            self.history_table.setItem(i, 5, QTableWidgetItem("查看"))

        self.log_action(f"搜索历史记录: '{keyword}'")

    def view_history_detail(self):
        """查看历史记录详情"""
        selected_row = self.history_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "警告", "请选择一条记录")
            return

        # 获取记录详情
        time = self.history_table.item(selected_row, 0).text()
        source = self.history_table.item(selected_row, 1).text()
        file = self.history_table.item(selected_row, 2).text()
        prediction = self.history_table.item(selected_row, 3).text()
        confidence = self.history_table.item(selected_row, 4).text()

        # 显示详情对话框
        detail_dialog = QMessageBox(self)
        detail_dialog.setWindowTitle("历史记录详情")
        detail_dialog.setText(f"""
        <b>时间:</b> {time}<br>
        <b>数据来源:</b> {source}<br>
        <b>文件:</b> {file}<br>
        <b>预测类型:</b> {prediction}<br>
        <b>置信度:</b> {confidence}
        """)
        detail_dialog.exec()

        self.log_action(f"查看历史记录详情: {file}")

    def generate_report(self):
        """生成报告"""
        report_path = f"{self.data_path_edit.text()}\\report.csv"
        if report_path:
            try:
                # 创建DataFrame保存结果
                data = []
                for row in range(self.history_table.rowCount()):
                    row_data = []
                    for col in range(self.history_table.columnCount()):
                        item = self.history_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    data.append(row_data)

                headers = ["时间", "数据类型", "文件名", "预测类型", "置信度", "操作"]
                df = pd.DataFrame(data, columns=headers)
                df.to_csv(report_path, index=False, encoding='utf_8_sig')

                self.log_action(f"结果已导出到: {report_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出结果失败: {str(e)}")

        QMessageBox.information(self, "成功", f"报告已生成: {report_path}")
        self.log_action(f"生成报告: -> {report_path}")

    def delete_history(self):
        """删除历史记录"""
        selected_row = self.history_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "警告", "请选择一条记录")
            return

        # 获取记录详情
        file_name = self.history_table.item(selected_row, 2).text()

        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除记录 '{file_name}' 吗?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 从表格中删除
            self.history_table.removeRow(selected_row)

            # 从history列表中删除
            for i, record in enumerate(self.history):
                if record["file"] == file_name:
                    del self.history[i]
                    break

            self.log_action(f"删除历史记录: {file_name}")

    def load_model(self):
        """加载模型"""
        file_path = self.model_path_edit.text()
        if file_path:
            try:
                # 更新模型路径
                self.model_path = file_path
                self.model = ClassificationModel(10,4)
                # 加载模型权重
                model_state = self.para_state_dict(self.model, file_path)
                self.model.load_state_dict(state_dict=model_state)

                # 更新模型
                self.model = PDTypePredictor(self.model,self.scaler)

                # 更新标签
                self.model_path_label.setText(f"当前模型: {self.model_path}")

                QMessageBox.information(self, "成功", "模型加载成功")
                self.log_action(f"模型加载成功: {file_path}")
                # 显示模型信息
                model_info = f"""
                   模型信息:
                   名称: {os.path.basename(file_path)}
                   大小: {os.path.getsize(file_path) / 1024 / 1024:.2f} MB
                   修改时间: {datetime.fromtimestamp(os.path.getmtime(file_path))}
                   """
                self.model_info_label.setText(model_info)
            except FileNotFoundError:
                QMessageBox.critical(self, "错误", f"模型文件不存在: {file_path}")
                self.log_action(f"模型文件不存在: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载模型失败: {str(e)}")
                self.log_action(f"加载模型失败: {str(e)}")

    def evaluate_model(self):
        """评估模型性能"""
        # 让用户选择测试数据集
        test_data_path = QFileDialog.getExistingDirectory(
            self, "选择测试数据集文件夹", ""
        )
        if not test_data_path:
            return

        self.log_action(f"开始评估模型，使用测试数据集: {test_data_path}")

        # 获取所有测试文件
        files = []
        for root, _, filenames in os.walk(test_data_path):
            for filename in filenames:
                if filename.endswith(('.txt')):  # 只处理文本文件
                    files.append(os.path.join(root, filename))

        if not files:
            QMessageBox.warning(self, "警告", "未找到有效的测试数据文件")
            return

        # 设置进度条
        self.progress_bar.setRange(0, len(files))
        self.progress_bar.setValue(0)

        # 初始化统计变量
        total_samples = 0
        correct_predictions = 0
        class_correct = {cls: 0 for cls in self.model.classes}
        class_total = {cls: 0 for cls in self.model.classes}
        confusion_matrix = np.zeros((len(self.model.classes), len(self.model.classes)), dtype=int)

        # 处理每个文件
        for i, file_path in enumerate(files):
            # 更新进度
            self.progress_bar.setValue(i + 1)
            self.status_bar.showMessage(f"处理文件: {os.path.basename(file_path)} ({i + 1}/{len(files)})")
            QApplication.processEvents()

            try:
                # 获取真实标签（从文件名或文件路径推断）
                # 这里假设文件夹结构为：类别名/文件名
                true_label = os.path.basename(os.path.dirname(file_path))
                if true_label not in self.model.classes:
                    # 如果文件夹名不是类别名，尝试从文件名推断
                    for cls in self.model.classes:
                        if cls in file_path:
                            true_label = cls
                            break
                    else:
                        # 无法确定真实标签，跳过
                        continue

                # 使用已有的 date_get_num 函数加载数据
                data = date_get_num(file_path)
                if not data:
                    self.log_action(f"文件 {file_path} 数据为空")
                    continue

                # 执行预测
                predicted_class, _, error_log = self.model.predict(extract_features(data))

                if error_log:
                    self.log_action(f"文件 {file_path} 预测错误: {error_log}")
                    continue

                # 更新统计
                total_samples += 1
                class_total[true_label] += 1

                if predicted_class == true_label:
                    correct_predictions += 1
                    class_correct[true_label] += 1

                # 更新混淆矩阵
                true_idx = self.model.classes.index(true_label)
                pred_idx = self.model.classes.index(predicted_class)
                confusion_matrix[true_idx][pred_idx] += 1

            except Exception as e:
                self.log_action(f"处理文件 {file_path} 时出错: {str(e)}")

        # 计算指标
        accuracy = correct_predictions / total_samples if total_samples > 0 else 0
        precision = {}
        recall = {}
        f1 = {}

        for cls in self.model.classes:
            tp = class_correct[cls]
            fp = class_total[cls] - tp
            fn = sum(confusion_matrix[self.model.classes.index(cls)]) - tp

            precision[cls] = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall[cls] = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1[cls] = 2 * (precision[cls] * recall[cls]) / (precision[cls] + recall[cls]) if (precision[cls] + recall[
                cls]) > 0 else 0

        # 显示评估结果
        result_dialog = QDialog(self)
        result_dialog.setWindowTitle("模型评估结果")
        result_dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(result_dialog)

        # 总体指标
        overall_layout = QHBoxLayout()
        overall_layout.addWidget(QLabel(f"总体准确率: {accuracy * 100:.2f}%"))
        overall_layout.addWidget(QLabel(f"测试样本数: {total_samples}"))
        layout.addLayout(overall_layout)

        # 类别指标表格
        table = QTableWidget()
        table.setRowCount(len(self.model.classes))
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["类别", "准确率", "精确率", "召回率", "F1分数"])

        for i, cls in enumerate(self.model.classes):
            table.setItem(i, 0, QTableWidgetItem(cls))
            table.setItem(i, 1, QTableWidgetItem(
                f"{class_correct[cls] / class_total[cls] * 100:.2f}%" if class_total[cls] > 0 else "N/A"))
            table.setItem(i, 2, QTableWidgetItem(f"{precision[cls] * 100:.2f}%"))
            table.setItem(i, 3, QTableWidgetItem(f"{recall[cls] * 100:.2f}%"))
            table.setItem(i, 4, QTableWidgetItem(f"{f1[cls] * 100:.2f}%"))

        layout.addWidget(table)

        # 混淆矩阵
        cm_layout = QHBoxLayout()
        cm_layout.addWidget(QLabel("混淆矩阵:"))

        cm_text = "真实标签\\预测标签\t" + "\t".join(self.model.classes) + "\n"
        for i, true_cls in enumerate(self.model.classes):
            cm_text += true_cls + "\t"
            for j, pred_cls in enumerate(self.model.classes):
                cm_text += str(confusion_matrix[i][j]) + "\t"
            cm_text += "\n"

        cm_text_edit = QTextEdit()
        cm_text_edit.setPlainText(cm_text)
        cm_text_edit.setReadOnly(True)
        cm_text_edit.setFont(QFont("Courier New", 10))
        layout.addWidget(cm_text_edit)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(result_dialog.close)
        layout.addWidget(close_btn)

        result_dialog.exec()

        # 记录评估结果
        self.log_action(f"模型评估完成: 总体准确率={accuracy * 100:.2f}%")
        for cls in self.model.classes:
            self.log_action(f"类别 '{cls}': 准确率={class_correct[cls] / class_total[cls] * 100:.2f}%, "
                            f"精确率={precision[cls] * 100:.2f}%, 召回率={recall[cls] * 100:.2f}%, F1分数={f1[cls] * 100:.2f}%")

    def save_settings(self):
        """保存系统设置为JSON文件"""
        # 收集当前设置
        settings = {
            "data_path": self.data_path_edit.text(),
            "model_path": self.model_path_edit.text(),  # 添加模型路径
            "file_path": self.file_path_edit.text(), # 添加文件路径
            "traindata_path":self.traindata_path_edit.text()
        }

        # 获取当前工作目录
        current_dir = os.getcwd()
        settings_path = os.path.join(current_dir, "system_settings.json")

        try:
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)

            self.log_action(f"系统设置已保存到: {settings_path}")
            QMessageBox.information(self, "成功", "系统设置已保存")
        except Exception as e:
            self.log_action(f"保存系统设置失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存设置失败: {str(e)}")

    def para_state_dict(self, model, model_save_path):
        """加载匹配的权重到模型"""
        model_state = deepcopy(model.state_dict())

        if not os.path.exists(model_save_path):
            self.log_action(f"警告: 权重文件不存在 {model_save_path}")
            return False

        try:
            # 加载保存的权重到CPU
            loaded_paras = torch.load(model_save_path, map_location='cpu')

            # 筛选可加载参数：名称匹配且维度一致
            matched_paras = {}
            for key in model_state:
                if key in loaded_paras:
                    if model_state[key].shape == loaded_paras[key].shape:
                        matched_paras[key] = loaded_paras[key]
                    else:

                        self.log_action(f"形状不匹配: {key} - 模型需要 {model_state[key].shape},加载的权重是 {loaded_paras[key].shape}")
                else:

                    self.log_action(f"缺失参数: {key}")

            self.log_action(f"成功加载 {len(matched_paras)}/{len(model_state)} 个参数")
            return matched_paras

        except Exception as e:
            print(f"加载权重失败: {str(e)}")
            return matched_paras

    def browse_traindata_path(self):
        """浏览训练数据或文件夹"""
        # 使用 getExistingDirectory 允许选择文件夹
        path = QFileDialog.getExistingDirectory(self, "选择数据文件夹")
        if path:
            self.traindata_path_edit.setText(path)
        self.log_action(f"浏览文件夹：{path}")

    def train_start(self):
        self.train(self.traindata_path_edit.text())
        self.log_action("开始训练")

    def train(self,DATA_DIR):
        # 加载数据
        X, y = load_data(DATA_DIR)
        if len(X) == 0:
            self.log_action("Error: No data loaded. Check your data directory and file formats.")
            return

        self.log_action(f"Loaded {len(X)} samples with {X.shape[1]} features")

        # 检查数据平衡性
        unique, counts = np.unique(y, return_counts=True)
        self.log_action(f"Class distribution:{dict(zip(unique, counts))}")

        # 第一步：划分训练集和测试集（在预处理之前）
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # 第二步：仅使用训练集拟合标准化器
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)  # 只在训练集上拟合

        # 第三步：使用相同的标准化器转换测试集
        X_test_scaled = scaler.transform(X_test)  # 不在测试集上拟合

        # 从训练集中划分验证集
        X_train_scaled, X_val_scaled, y_train, y_val = train_test_split(
            X_train_scaled, y_train, test_size=0.2, random_state=42, stratify=y_train
        )

        # 创建数据集和数据加载器
        train_dataset = FeatureDataset(X_train_scaled, y_train)
        val_dataset = FeatureDataset(X_val_scaled, y_val)
        test_dataset = FeatureDataset(X_test_scaled, y_test)

        batch_size = 32
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)
        test_loader = DataLoader(test_dataset, batch_size=batch_size)

        # 设置设备
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.log_action(f"Using device: {device}")

        # 初始化模型
        input_size = X_train_scaled.shape[1]
        num_classes = len(np.unique(y))
        model = ClassificationModel(input_size, num_classes).to(device)

        # 定义损失函数和优化器
        criterion = torch.nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

        # 训练模型
        self.log_action("Starting training...")
        model = train_model(model, train_loader, val_loader, criterion, optimizer, device,num_epochs=100, patience=10 ,pth=f"{self.data_path_edit.text()}/best_model.pth")

        # 保存模型
        # 保存状态字典（训练完成后执行）
        torch.save(self.model.model.state_dict(), "classification_model_state.pth")
        self.log_action("Model saved as classification_model.pth")
        # 评估模型
        self.log_action("\nEvaluating on test set...")
        evaluate_model(model, test_loader, device)


        # 保存标准化器
        joblib.dump(scaler, 'scaler.pkl')
        self.log_action("Scaler saved as scaler.pkl")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())