from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLocale, QSettings, Qt, QThreadPool
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..service import DiagnosisService
from ..storage import HistoryRecord, HistoryRepository
from ..types import BatchDiagnosisItem
from .charts import ProbabilityCanvas, PrpdCanvas, WaveformCanvas
from .formatting import display_time
from .theme import build_stylesheet
from .workers import (
    BatchDiagnosisTask,
    HistoryExportOutcome,
    HistoryExportTask,
    SingleDiagnosisOutcome,
    SingleDiagnosisTask,
)

PAGE_SIZE = 100


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: DiagnosisService,
        history: HistoryRepository,
        *,
        model_path: Path,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.history = history
        self.model_path = model_path
        self.settings = settings or QSettings()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(1)
        self.current_batch_task: BatchDiagnosisTask | None = None
        self.current_history_export: HistoryExportTask | None = None
        self.history_offset = 0
        self.dark_theme = self.settings.value("ui/dark_theme", False, type=bool)

        self.setWindowTitle("局部放电类型智能诊断")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 720)
        self.setStyleSheet(build_stylesheet(dark=self.dark_theme))
        self._build_shell()
        self._install_shortcuts()
        self._restore_settings()
        self.refresh_history()

    def _build_shell(self) -> None:
        root = QWidget(objectName="AppRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QWidget(objectName="Sidebar")
        sidebar.setFixedWidth(238)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 22, 16, 18)
        title = QLabel("局放智能诊断", objectName="AppTitle")
        subtitle = QLabel("Partial Discharge", objectName="MutedLabel")
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(22)
        self.navigation = QListWidget(objectName="Navigation")
        self.navigation.setAccessibleName("主导航")
        self.navigation.setAccessibleDescription("切换诊断、批量、历史和设置页面")
        self.navigation.setSpacing(2)
        self.navigation.addItems(["诊断工作台", "批量诊断", "历史与报告", "模型与设置"])
        sidebar_layout.addWidget(self.navigation)
        sidebar_layout.addStretch()
        model_caption = QLabel("当前模型", objectName="MutedLabel")
        self.sidebar_model = QLabel(self.service.engine.bundle.model_version)
        self.sidebar_model.setWordWrap(True)
        sidebar_layout.addWidget(model_caption)
        sidebar_layout.addWidget(self.sidebar_model)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 18, 26, 14)
        content_layout.setSpacing(14)
        header = QHBoxLayout()
        self.page_title = QLabel("诊断工作台", objectName="PageTitle")
        self.model_badge = QLabel(
            f"● 模型就绪 · {self.service.engine.device.type}", objectName="MutedLabel"
        )
        header.addWidget(self.page_title)
        header.addStretch()
        header.addWidget(self.model_badge)
        content_layout.addLayout(header)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_diagnosis_page())
        self.pages.addWidget(self._build_batch_page())
        self.pages.addWidget(self._build_history_page())
        self.pages.addWidget(self._build_settings_page())
        content_layout.addWidget(self.pages)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("模型已加载，可以开始诊断")

        self.navigation.currentRowChanged.connect(self._change_page)
        self.navigation.setCurrentRow(0)

    def _build_diagnosis_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        input_card, input_layout = card()
        input_header = QHBoxLayout()
        input_header.addWidget(QLabel("信号输入", objectName="SectionTitle"))
        input_header.addStretch()
        input_header.addWidget(QLabel("支持 UTF-8 / ASCII TXT", objectName="MutedLabel"))
        input_layout.addLayout(input_header)
        input_row = QHBoxLayout()
        self.single_path = QLineEdit()
        self.single_path.setPlaceholderText("选择一维信号 TXT 文件")
        self.single_path.setAccessibleName("单次诊断文件路径")
        self.single_path.setAccessibleDescription("输入或选择要诊断的一维 TXT 信号文件")
        self.single_browse = QPushButton("选择文件")
        self.single_browse.clicked.connect(self._browse_single)
        self.diagnose_button = QPushButton("开始诊断", objectName="PrimaryButton")
        self.diagnose_button.clicked.connect(self.start_single_diagnosis)
        input_row.addWidget(self.single_path, 1)
        input_row.addWidget(self.single_browse)
        input_row.addWidget(self.diagnose_button)
        input_layout.addLayout(input_row)
        layout.addWidget(input_card)

        splitter = QSplitter(Qt.Horizontal)
        self.diagnosis_splitter = splitter
        charts_card, charts_layout = card()
        tabs = QTabWidget()
        self.waveform_canvas = WaveformCanvas()
        self.prpd_canvas = PrpdCanvas()
        tabs.addTab(self.waveform_canvas, "波形")
        tabs.addTab(self.prpd_canvas, "PRPD")
        charts_layout.addWidget(tabs)
        splitter.addWidget(charts_card)

        result_card, result_layout = card()
        result_card.setMinimumWidth(340)
        result_header = QHBoxLayout()
        result_header.addWidget(QLabel("模型建议", objectName="SectionTitle"))
        result_header.addStretch()
        self.result_state = QLabel("等待诊断", objectName="MutedLabel")
        result_header.addWidget(self.result_state)
        result_layout.addLayout(result_header)
        self.result_label = QLabel("尚无结果", objectName="ResultLabel")
        self.result_label.setWordWrap(True)
        self.result_label.setAccessibleName("模型建议结果")
        self.result_label.setAccessibleDescription("显示模型建议的局部放电缺陷类别")
        self.confidence_label = QLabel("置信度 —", objectName="ConfidenceLabel")
        self.confidence_label.setAccessibleName("模型置信度")
        self.warning_label = QLabel("结果仅供辅助判断，请结合现场信息复核。", objectName="WarningLabel")
        self.warning_label.setAccessibleName("诊断提示")
        self.warning_label.setWordWrap(True)
        self.probability_canvas = ProbabilityCanvas()
        result_layout.addWidget(self.result_label)
        result_layout.addWidget(self.confidence_label)
        result_layout.addWidget(self.warning_label)
        result_layout.addWidget(self.probability_canvas, 1)
        splitter.addWidget(result_card)
        splitter.setSizes([720, 390])
        layout.addWidget(splitter, 1)

        features_card, features_layout = card()
        features_layout.addWidget(QLabel("特征摘要", objectName="SectionTitle"))
        self.feature_table = QTableWidget(4, 5)
        self.feature_table.setAccessibleName("信号特征摘要表")
        self.feature_table.setAccessibleDescription("显示模型使用的十项信号特征及数值")
        self.feature_table.setVerticalHeaderLabels(["特征", "数值", "特征", "数值"])
        self.feature_table.horizontalHeader().setVisible(False)
        self.feature_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.feature_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.feature_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.feature_table.setMaximumHeight(176)
        features_layout.addWidget(self.feature_table)
        layout.addWidget(features_card)
        return page

    def _build_batch_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        control_card, control_layout = card()
        control_layout.addWidget(QLabel("批量任务", objectName="SectionTitle"))
        row = QHBoxLayout()
        self.batch_path = QLineEdit()
        self.batch_path.setAccessibleName("批量诊断目录路径")
        self.batch_path.setAccessibleDescription("选择包含 TXT 信号文件的目录")
        self.batch_path.setPlaceholderText("选择包含 TXT 文件的目录")
        browse = QPushButton("选择目录")
        browse.clicked.connect(self._browse_batch)
        self.batch_start = QPushButton("开始处理", objectName="PrimaryButton")
        self.batch_start.clicked.connect(self.start_batch_diagnosis)
        self.batch_cancel = QPushButton("取消")
        self.batch_cancel.setEnabled(False)
        self.batch_cancel.clicked.connect(self.cancel_batch_diagnosis)
        row.addWidget(self.batch_path, 1)
        row.addWidget(browse)
        row.addWidget(self.batch_start)
        row.addWidget(self.batch_cancel)
        control_layout.addLayout(row)
        self.batch_progress = QProgressBar()
        self.batch_progress.setValue(0)
        control_layout.addWidget(self.batch_progress)
        layout.addWidget(control_card)

        table_card, table_layout = card()
        table_header = QHBoxLayout()
        table_header.addWidget(QLabel("处理结果", objectName="SectionTitle"))
        table_header.addStretch()
        self.batch_summary = QLabel("尚未开始", objectName="MutedLabel")
        table_header.addWidget(self.batch_summary)
        table_layout.addLayout(table_header)
        self.batch_table = QTableWidget(0, 5)
        self.batch_table.setAccessibleName("批量诊断结果表")
        self.batch_table.setAccessibleDescription("逐项显示批量文件的诊断状态和结果")
        self.batch_table.setHorizontalHeaderLabels(["文件", "状态", "诊断类型", "置信度", "说明"])
        self.batch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.batch_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.batch_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table_layout.addWidget(self.batch_table)
        layout.addWidget(table_card, 1)
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        toolbar_card, toolbar = card()
        toolbar.addWidget(QLabel("诊断历史", objectName="SectionTitle"))
        row = QHBoxLayout()
        self.history_query = QLineEdit()
        self.history_query.setAccessibleName("历史记录搜索")
        self.history_query.setPlaceholderText("搜索文件、诊断类型或模型版本")
        self.history_query.returnPressed.connect(self._search_history)
        search = QPushButton("搜索")
        search.clicked.connect(self._search_history)
        detail = QPushButton("查看详情")
        detail.clicked.connect(self.show_history_detail)
        self.history_export_button = QPushButton("导出 CSV")
        self.history_export_button.clicked.connect(self.export_history)
        delete = QPushButton("删除", objectName="DangerButton")
        delete.clicked.connect(self.delete_history)
        row.addWidget(self.history_query, 1)
        row.addWidget(search)
        row.addWidget(detail)
        row.addWidget(self.history_export_button)
        row.addWidget(delete)
        toolbar.addLayout(row)
        layout.addWidget(toolbar_card)

        table_card, table_layout = card()
        summary_row = QHBoxLayout()
        self.history_summary = QLabel(objectName="MutedLabel")
        summary_row.addWidget(self.history_summary)
        summary_row.addStretch()
        self.history_previous = QPushButton("上一页")
        self.history_previous.setAccessibleName("历史记录上一页")
        self.history_previous.clicked.connect(self._previous_history_page)
        self.history_page_label = QLabel(objectName="MutedLabel")
        self.history_page_label.setAccessibleName("历史记录页码")
        self.history_next = QPushButton("下一页")
        self.history_next.setAccessibleName("历史记录下一页")
        self.history_next.clicked.connect(self._next_history_page)
        summary_row.addWidget(self.history_previous)
        summary_row.addWidget(self.history_page_label)
        summary_row.addWidget(self.history_next)
        table_layout.addLayout(summary_row)
        self.history_table = QTableWidget(0, 6)
        self.history_table.setAccessibleName("诊断历史记录表")
        self.history_table.setAccessibleDescription("显示已保存的诊断和错误记录")
        self.history_table.setHorizontalHeaderLabels(
            ["时间", "来源", "模型建议", "置信度", "模型版本", "状态"]
        )
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.doubleClicked.connect(self.show_history_detail)
        table_layout.addWidget(self.history_table)
        layout.addWidget(table_card, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        model_card, model_layout = card()
        model_layout.addWidget(QLabel("模型信息", objectName="SectionTitle"))
        model_layout.addWidget(QLabel(f"版本：{self.service.engine.bundle.model_version}"))
        model_layout.addWidget(QLabel(f"设备：{self.service.engine.device}"))
        path_label = QLabel(f"Bundle：{self.model_path}", objectName="MutedLabel")
        path_label.setWordWrap(True)
        model_layout.addWidget(path_label)
        bundle = self.service.engine.bundle
        self.model_contract_label = QLabel(
            f"特征模式：{bundle.feature_schema} · "
            f"采样率：{QLocale().toString(bundle.sampling_rate_hz)} Hz · 输入：数组或 TXT",
            objectName="MutedLabel",
        )
        self.model_contract_label.setAccessibleName("模型输入契约")
        model_layout.addWidget(self.model_contract_label)
        layout.addWidget(model_card)

        storage_card, storage_layout = card()
        storage_layout.addWidget(QLabel("数据与外观", objectName="SectionTitle"))
        database = QLabel(f"历史数据库：{self.history.path}", objectName="MutedLabel")
        database.setWordWrap(True)
        storage_layout.addWidget(database)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("界面主题"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["浅色", "深色"])
        self.theme_combo.setCurrentIndex(1 if self.dark_theme else 0)
        self.theme_combo.setAccessibleName("界面主题")
        self.theme_combo.currentIndexChanged.connect(self._change_theme)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        storage_layout.addLayout(theme_row)
        layout.addWidget(storage_card)

        training_card, training_layout = card()
        training_layout.addWidget(QLabel("模型训练（实验性）", objectName="SectionTitle"))
        note = QLabel(
            "训练能力已移至 pd_diagnosis.experimental.training。它支持进度回调、取消和新 bundle 输出，"
            "但首版不承诺接口向后兼容。建议在独立环境中运行训练。",
            objectName="MutedLabel",
        )
        note.setWordWrap(True)
        training_layout.addWidget(note)
        layout.addWidget(training_card)
        layout.addStretch()
        return page

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._browse_single)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.start_single_diagnosis)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.history_query.setFocus)

    def _change_page(self, index: int) -> None:
        if index < 0:
            return
        titles = ["诊断工作台", "批量诊断", "历史与报告", "模型与设置"]
        self.pages.setCurrentIndex(index)
        self.page_title.setText(titles[index])
        if index == 2:
            self.refresh_history()

    def _browse_single(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择信号 TXT", "", "文本信号 (*.txt)")
        if path:
            self.single_path.setText(path)

    def _browse_batch(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择批量信号目录")
        if path:
            self.batch_path.setText(path)

    def start_single_diagnosis(self) -> None:
        path = self.single_path.text().strip()
        if not path:
            QMessageBox.warning(self, "缺少输入", "请先选择 TXT 信号文件。")
            return
        self._set_single_running(True)
        self.result_state.setText("分析中…")
        self.statusBar().showMessage("正在提取特征并执行模型推理…")
        task = SingleDiagnosisTask(self.service, path)
        task.signals.result.connect(self._show_single_result)
        task.signals.error.connect(self._show_single_error)
        task.signals.finished.connect(self._finish_single)
        self.thread_pool.start(task)

    def _show_single_result(self, outcome: SingleDiagnosisOutcome) -> None:
        result = outcome.result
        try:
            self.waveform_canvas.plot_signal(outcome.samples)
            self.prpd_canvas.plot_signal(
                outcome.samples, self.service.engine.bundle.sampling_rate_hz
            )
        except Exception as exc:
            self.statusBar().showMessage(f"诊断完成，但图表加载失败：{exc}")
        self.result_label.setText(result.label)
        self.confidence_label.setText(f"置信度 {result.confidence:.1%}")
        self.result_state.setText("诊断完成")
        self.warning_label.setText(
            "\n".join(result.warnings)
            if result.warnings
            else "结果仅供辅助判断，请结合现场信息复核。"
        )
        self.probability_canvas.plot_probabilities(dict(result.probabilities))
        entries = list(result.features.items())
        for index, (name, value) in enumerate(entries):
            row_offset = 0 if index < 5 else 2
            column = index % 5
            self.feature_table.setItem(row_offset, column, QTableWidgetItem(name))
            self.feature_table.setItem(
                row_offset + 1, column, QTableWidgetItem(format_feature(value))
            )
        self.statusBar().showMessage(f"诊断完成：{result.label}（{result.confidence:.1%}）", 8000)
        self.refresh_history()

    def _set_single_running(self, running: bool) -> None:
        self.single_path.setEnabled(not running)
        self.single_browse.setEnabled(not running)
        self.diagnose_button.setEnabled(not running)

    def _finish_single(self) -> None:
        self._set_single_running(False)

    def _show_single_error(self, message: str) -> None:
        self.result_state.setText("诊断失败")
        self.statusBar().showMessage("诊断失败", 5000)
        QMessageBox.critical(self, "诊断失败", message)
        self.refresh_history()

    def start_batch_diagnosis(self) -> None:
        directory = Path(self.batch_path.text().strip())
        if not directory.is_dir():
            QMessageBox.warning(self, "目录无效", "请选择有效的批量信号目录。")
            return
        paths = [str(path) for path in sorted(directory.rglob("*.txt"))]
        if not paths:
            QMessageBox.information(self, "没有文件", "目录中没有找到 TXT 信号文件。")
            return
        self.batch_table.setRowCount(len(paths))
        for row, path in enumerate(paths):
            self.batch_table.setItem(row, 0, QTableWidgetItem(path))
            self.batch_table.setItem(row, 1, QTableWidgetItem("等待"))
        self.batch_progress.setRange(0, len(paths))
        self.batch_progress.setValue(0)
        self.batch_summary.setText(f"共 {len(paths)} 个文件")
        self.batch_start.setEnabled(False)
        self.batch_cancel.setEnabled(True)
        task = BatchDiagnosisTask(self.service, paths)
        task.signals.item.connect(self._show_batch_item)
        task.signals.progress.connect(self._show_batch_progress)
        task.signals.finished.connect(self._finish_batch)
        self.current_batch_task = task
        self.thread_pool.start(task)

    def cancel_batch_diagnosis(self) -> None:
        if self.current_batch_task is not None:
            self.current_batch_task.cancel()
            self.batch_summary.setText("正在取消，等待当前文件结束…")
            self.batch_cancel.setEnabled(False)

    def _show_batch_item(self, row: int, item: BatchDiagnosisItem) -> None:
        if item.result is not None:
            result = item.result
            values = ["成功", result.label, f"{result.confidence:.1%}", "；".join(result.warnings)]
        else:
            values = ["失败", "—", "—", item.error or "未知错误"]
        for column, value in enumerate(values, start=1):
            self.batch_table.setItem(row, column, QTableWidgetItem(value))

    def _show_batch_progress(self, completed: int, total: int) -> None:
        self.batch_progress.setValue(completed)
        self.batch_summary.setText(f"已处理 {completed}/{total}")

    def _finish_batch(self) -> None:
        completed = self.batch_progress.value()
        total = self.batch_progress.maximum()
        cancelled = completed < total
        self.batch_summary.setText(
            f"已取消，完成 {completed}/{total}" if cancelled else f"处理完成，共 {total} 个文件"
        )
        self.batch_start.setEnabled(True)
        self.batch_cancel.setEnabled(False)
        self.current_batch_task = None
        self.refresh_history()
        self.statusBar().showMessage("批量任务已结束", 5000)

    def refresh_history(self) -> None:
        if not hasattr(self, "history_table"):
            return
        query = self.history_query.text().strip()
        total = self.history.count(query=query)
        if self.history_offset >= total and self.history_offset > 0:
            self.history_offset = max(0, ((max(total, 1) - 1) // PAGE_SIZE) * PAGE_SIZE)
        records = self.history.list(
            limit=PAGE_SIZE,
            offset=self.history_offset,
            query=query,
        )
        self.history_table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                display_time(record.created_at),
                record.source_id or "—",
                record.label or "—",
                f"{record.confidence:.1%}" if record.confidence is not None else "—",
                record.model_version,
                "成功" if record.status == "success" else "失败",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, record.run_id)
                self.history_table.setItem(row, column, item)
        start = self.history_offset + 1 if records else 0
        end = self.history_offset + len(records)
        page = self.history_offset // PAGE_SIZE + 1
        page_count = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.history_summary.setText(f"显示 {start}–{end} 条 · 当前筛选共 {total} 条")
        self.history_page_label.setText(f"第 {page}/{page_count} 页")
        self.history_previous.setEnabled(self.history_offset > 0)
        self.history_next.setEnabled(end < total)

    def _search_history(self) -> None:
        self.history_offset = 0
        self.refresh_history()

    def _previous_history_page(self) -> None:
        self.history_offset = max(0, self.history_offset - PAGE_SIZE)
        self.refresh_history()

    def _next_history_page(self) -> None:
        if self.history_next.isEnabled():
            self.history_offset += PAGE_SIZE
            self.refresh_history()

    def _selected_history(self) -> HistoryRecord | None:
        row = self.history_table.currentRow()
        if row < 0:
            return None
        item = self.history_table.item(row, 0)
        return self.history.get(item.data(Qt.UserRole)) if item else None

    def show_history_detail(self, *_args: object) -> None:
        record = self._selected_history()
        if record is None:
            QMessageBox.information(self, "选择记录", "请先选择一条诊断记录。")
            return
        probability_text = "\n".join(
            f"{name}: {value:.1%}" for name, value in record.probabilities.items()
        ) or "—"
        message = (
            f"时间：{display_time(record.created_at)}\n"
            f"来源：{record.source_id or '—'}\n"
            f"模型：{record.model_version}\n"
            f"结果：{record.label or '失败'}\n"
            f"置信度：{record.confidence:.1%}\n\n各类别概率：\n{probability_text}"
            if record.confidence is not None
            else f"时间：{display_time(record.created_at)}\n来源：{record.source_id or '—'}\n错误：{record.error_message}"
        )
        QMessageBox.information(self, "诊断详情", message)

    def delete_history(self) -> None:
        selected_rows = sorted({index.row() for index in self.history_table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.information(self, "选择记录", "请先选择要删除的诊断记录。")
            return
        answer = QMessageBox.question(
            self, "确认删除", f"确定删除选中的 {len(selected_rows)} 条记录吗？此操作无法撤销。"
        )
        if answer != QMessageBox.Yes:
            return
        run_ids = [self.history_table.item(row, 0).data(Qt.UserRole) for row in selected_rows]
        self.history.delete(run_ids)
        self.refresh_history()

    def export_history(self) -> None:
        query = self.history_query.text().strip()
        if self.history.count(query=query) == 0:
            QMessageBox.information(self, "没有记录", "当前没有可导出的诊断记录。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出诊断历史", "diagnosis-history.csv", "CSV (*.csv)")
        if not path:
            return
        self.history_export_button.setEnabled(False)
        self.statusBar().showMessage("正在后台导出诊断历史…")
        task = HistoryExportTask(self.history, path, query=query)
        task.signals.progress.connect(self._show_history_export_progress)
        task.signals.result.connect(self._show_history_export_result)
        task.signals.error.connect(self._show_history_export_error)
        task.signals.finished.connect(self._finish_history_export)
        self.current_history_export = task
        self.thread_pool.start(task)

    def _show_history_export_progress(self, completed: int, total: int) -> None:
        self.statusBar().showMessage(f"正在导出诊断历史：{completed}/{total}")

    def _show_history_export_result(self, outcome: HistoryExportOutcome) -> None:
        self.statusBar().showMessage(
            f"已导出 {outcome.count} 条记录：{outcome.path}", 6000
        )

    def _show_history_export_error(self, message: str) -> None:
        QMessageBox.critical(self, "导出失败", message)
        self.statusBar().showMessage("诊断历史导出失败", 6000)

    def _finish_history_export(self) -> None:
        self.history_export_button.setEnabled(True)
        self.current_history_export = None

    def _change_theme(self, index: int) -> None:
        self.dark_theme = index == 1
        self.setStyleSheet(build_stylesheet(dark=self.dark_theme))
        self.settings.setValue("ui/dark_theme", self.dark_theme)
        for canvas in (self.waveform_canvas, self.prpd_canvas, self.probability_canvas):
            canvas.apply_theme(self.dark_theme)

    def _restore_settings(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        splitter_state = self.settings.value("window/diagnosis_splitter")
        if splitter_state is not None:
            self.diagnosis_splitter.restoreState(splitter_state)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.setValue("ui/dark_theme", self.dark_theme)
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue(
            "window/diagnosis_splitter", self.diagnosis_splitter.saveState()
        )
        self.settings.sync()
        super().closeEvent(event)


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(objectName="Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    return frame, layout


def format_feature(value: float) -> str:
    absolute = abs(value)
    if absolute >= 100_000 or (absolute and absolute < 0.001):
        return f"{value:.4e}"
    return f"{value:.4f}"
