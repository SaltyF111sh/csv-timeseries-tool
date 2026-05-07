"""时间对齐对话框：时间列识别、交集预览、合并导出。"""

from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.aligner import (
    detect_freq,
    detect_time_column,
    get_time_range,
    merge_files,
    compute_intersection_info,
)
from core.config_manager import ConfigManager
from core.csv_handler import ColumnState
from core.version_store import VersionStore

# ---------- 对话框样式 ----------
DIALOG_STYLE = """
QDialog {
    background-color: #f5f6fa;
}
QLabel#section_title {
    font-size: 14px;
    font-weight: bold;
    color: #2d3436;
    margin-bottom: 4px;
}
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    color: #2d3436;
    border: 1px solid #dfe6e9;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    background: #fff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QTableWidget {
    background: white;
    border: 1px solid #dfe6e9;
    border-radius: 4px;
    gridline-color: #dfe6e9;
    font-size: 12px;
    outline: none;
}
QTableWidget::item {
    padding: 4px 6px;
}
QHeaderView::section {
    background-color: #2d3436;
    color: white;
    padding: 5px 8px;
    border: none;
    font-weight: bold;
    font-size: 12px;
}
QComboBox {
    border: 1px solid #dfe6e9;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 12px;
    background: white;
}
QLineEdit {
    border: 1px solid #dfe6e9;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 12px;
    background: white;
}
QLabel#info_label {
    color: #636e72;
    font-size: 12px;
    padding: 4px 8px;
    background: #dfe6e9;
    border-radius: 4px;
}
QPushButton#btn_preview {
    background-color: #0984e3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#btn_preview:hover {
    background-color: #0773c5;
}
QPushButton#btn_preview:pressed {
    background-color: #065ea8;
}
QPushButton#btn_export {
    background-color: #00b894;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#btn_export:hover {
    background-color: #00a381;
}
QPushButton#btn_export:pressed {
    background-color: #008e6e;
}
QFrame#separator {
    background-color: #dfe6e9;
    max-height: 1px;
}
"""

PREVIEW_ROWS = 10


class TimeAlignDialog(QDialog):
    """时间对齐与合并导出对话框。"""

    def __init__(
        self,
        folder: Path,
        file_states: dict[str, list[ColumnState]],
        version_store: VersionStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._folder = folder
        self._file_states = file_states
        self._version_store = version_store
        # 有序文件名列表（按原始文件列表顺序）
        self._filenames = list(file_states.keys())
        # 每文件的完整列名（首次读取时缓存）
        self._all_columns: dict[str, list[str]] = {}
        self._merged_df: pd.DataFrame | None = None

        self._init_ui()
        self._load_file_info()

    # ======== UI 初始化 ========

    def _init_ui(self) -> None:
        self.setWindowTitle("时间对齐与合并导出")
        self.resize(950, 750)
        self.setMinimumSize(850, 600)
        self.setStyleSheet(DIALOG_STYLE)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # 1. 时间列识别表格
        root.addWidget(self._create_time_col_section())

        # 2. 时间交集预览
        root.addWidget(self._create_intersection_section())

        # 3. 合并设置
        root.addWidget(self._create_merge_settings())

        # 4. 预览表格
        self._preview_table = QTableWidget()
        self._preview_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._preview_table.horizontalHeader().setMinimumSectionSize(60)
        self._preview_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        root.addWidget(self._preview_table, stretch=1)

        # 5. 底部按钮
        root.addWidget(self._create_bottom_buttons())

    def _create_time_col_section(self) -> QGroupBox:
        group = QGroupBox("1. 时间列识别")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)

        self._time_table = QTableWidget()
        self._time_table.setColumnCount(4)
        self._time_table.setHorizontalHeaderLabels(
            ["文件名", "时间列", "时间范围（最小）", "时间范围（最大）"]
        )
        self._time_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._time_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._time_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._time_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._time_table.setMinimumHeight(100)
        layout.addWidget(self._time_table)

        return group

    def _create_intersection_section(self) -> QGroupBox:
        group = QGroupBox("2. 时间交集预览")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._label_intersection = QLabel("请先确认时间列选择，系统将自动计算交集")
        self._label_intersection.setWordWrap(True)
        self._label_intersection.setStyleSheet(
            "color: #636e72; font-size: 12px; padding: 6px 10px;"
            "background: #dfe6e9; border-radius: 4px;"
        )
        layout.addWidget(self._label_intersection)

        info_row = QHBoxLayout()
        info_row.setSpacing(12)

        self._btn_detect_freq = QPushButton("自动检测频率")
        self._btn_detect_freq.setStyleSheet(
            "background: transparent; color: #0984e3; border: 1px solid #0984e3;"
            "border-radius: 3px; padding: 4px 12px; font-size: 12px;"
        )
        info_row.addWidget(self._btn_detect_freq)

        cfg = ConfigManager.instance()
        default_freq = cfg.get("default_freq", "auto")
        freq_display = "1H" if default_freq == "auto" else default_freq
        self._freq_edit = QLineEdit(freq_display)
        self._freq_edit.setFixedWidth(120)
        self._freq_edit.setPlaceholderText("如 1H / 15min / 1D")
        info_row.addWidget(QLabel("步长:"))
        info_row.addWidget(self._freq_edit)
        info_row.addStretch()

        layout.addLayout(info_row)
        return group

    def _create_merge_settings(self) -> QGroupBox:
        group = QGroupBox("3. 合并设置")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        layout.addWidget(QLabel("输出文件名:"))

        from datetime import date
        tmpl = ConfigManager.instance().get("output_filename_template", "merged_{date}")
        default_name = tmpl.replace("{date}", date.today().strftime("%Y%m%d"))
        self._output_edit = QLineEdit(default_name)
        self._output_edit.setMinimumWidth(220)
        layout.addWidget(self._output_edit)

        layout.addStretch()
        return group

    def _create_bottom_buttons(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)

        # 实际上我们放按钮就行
        self._btn_preview = QPushButton("预览合并结果")
        self._btn_preview.setObjectName("btn_preview")

        self._btn_export = QPushButton("导出 CSV")
        self._btn_export.setObjectName("btn_export")

        layout.addStretch()
        layout.addWidget(self._btn_preview)
        layout.addWidget(self._btn_export)

        return widget

    # ======== 数据加载 ========

    def _load_file_info(self) -> None:
        """读取每个文件的列名，自动检测时间列。"""
        self._time_table.setRowCount(len(self._filenames))

        for i, filename in enumerate(self._filenames):
            filepath = self._folder / filename
            try:
                df = pd.read_csv(filepath, nrows=5)  # 只读前几行用于检测
            except Exception:
                continue

            columns = df.columns.tolist()
            self._all_columns[filename] = columns

            # 自动检测时间列
            detected = detect_time_column(df)

            # 文件名
            name_item = QTableWidgetItem(filename)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._time_table.setItem(i, 0, name_item)

            # 时间列下拉框
            combo = QComboBox()
            combo.addItems(columns)
            if detected and detected in columns:
                combo.setCurrentText(detected)
            combo.currentTextChanged.connect(self._on_time_col_changed)
            self._time_table.setCellWidget(i, 1, combo)

            # 时间范围
            time_col = combo.currentText()
            try:
                full_df = pd.read_csv(filepath)
                min_t, max_t = get_time_range(full_df, time_col)
            except Exception:
                min_t, max_t = ("读取失败", "读取失败")

            min_item = QTableWidgetItem(min_t)
            min_item.setFlags(min_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._time_table.setItem(i, 2, min_item)

            max_item = QTableWidgetItem(max_t)
            max_item.setFlags(max_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._time_table.setItem(i, 3, max_item)

        self._refresh_intersection_info()
        # 连接信号
        self._btn_detect_freq.clicked.connect(self._on_detect_freq)
        self._btn_preview.clicked.connect(self._on_preview)
        self._btn_export.clicked.connect(self._on_export)

    # ======== 事件 ========

    def _on_time_col_changed(self, _text: str) -> None:
        """时间列下拉框变更时，更新该行的时间范围并刷新交集。"""
        combo = self.sender()
        if not isinstance(combo, QComboBox):
            return

        # 找到该 combo 所在行
        for i in range(self._time_table.rowCount()):
            if self._time_table.cellWidget(i, 1) is combo:
                filename = self._filenames[i]
                time_col = combo.currentText()
                filepath = self._folder / filename
                try:
                    full_df = pd.read_csv(filepath)
                    min_t, max_t = get_time_range(full_df, time_col)
                except Exception:
                    min_t, max_t = ("读取失败", "读取失败")

                min_item = QTableWidgetItem(min_t)
                min_item.setFlags(min_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._time_table.setItem(i, 2, min_item)

                max_item = QTableWidgetItem(max_t)
                max_item.setFlags(max_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._time_table.setItem(i, 3, max_item)
                break

        self._refresh_intersection_info()

    def _on_detect_freq(self) -> None:
        """自动检测所有文件的时间频率（取第一份有效结果）。"""
        for i, filename in enumerate(self._filenames):
            combo = self._time_table.cellWidget(i, 1)
            if not isinstance(combo, QComboBox):
                continue
            time_col = combo.currentText()
            filepath = self._folder / filename
            try:
                df = pd.read_csv(filepath)
                freq = detect_freq(df[time_col])
                self._freq_edit.setText(freq)
                return
            except Exception:
                continue

        QMessageBox.information(self, "检测失败", "未能自动检测时间频率，请手动输入。")

    def _refresh_intersection_info(self) -> None:
        """刷新时间交集预览信息。"""
        filepaths, time_cols = self._gather_file_info()
        if len(filepaths) < 2:
            self._label_intersection.setText("需要至少2个文件")
            return

        try:
            info = compute_intersection_info(
                filepaths,
                [self._file_states[fn] for fn in self._filenames],
                time_cols,
            )
        except Exception as exc:
            self._label_intersection.setText(f"计算交集失败: {exc}")
            return

        if info is None:
            self._label_intersection.setText("⚠ 各文件时间范围无交集，无法合并")
            return

        min_t, max_t, rows = info
        self._label_intersection.setText(
            f"交集范围: {min_t}  ~  {max_t}  |  预计数据行数: {rows}"
        )

    def _gather_file_info(self) -> tuple[list[Path], list[str]]:
        """收集当前对话框中的文件路径和时间列选择。"""
        filepaths: list[Path] = []
        time_cols: list[str] = []

        for i in range(self._time_table.rowCount()):
            filename = self._filenames[i]
            combo = self._time_table.cellWidget(i, 1)
            if isinstance(combo, QComboBox):
                time_cols.append(combo.currentText())
                filepaths.append(self._folder / filename)

        return filepaths, time_cols

    def _on_preview(self) -> None:
        """预览合并结果（前10行）。"""
        filepaths, time_cols = self._gather_file_info()
        if len(filepaths) < 2:
            QMessageBox.warning(self, "提示", "需要至少2个文件才能合并。")
            return

        freq = self._freq_edit.text().strip()
        if not freq:
            QMessageBox.warning(self, "提示", "请输入时间步长。")
            return

        try:
            self._merged_df = merge_files(
                filepaths,
                [self._file_states[fn] for fn in self._filenames],
                time_cols,
                freq,
            )
        except Exception as exc:
            QMessageBox.warning(self, "合并失败", str(exc))
            return

        # 显示前10行
        preview = self._merged_df.head(PREVIEW_ROWS)
        self._show_preview(preview)

    def _on_export(self) -> None:
        """导出合并结果到 CSV。"""
        filepaths, time_cols = self._gather_file_info()
        if len(filepaths) < 2:
            QMessageBox.warning(self, "提示", "需要至少2个文件才能合并。")
            return

        freq = self._freq_edit.text().strip()
        if not freq:
            QMessageBox.warning(self, "提示", "请输入时间步长。")
            return

        # 选择保存路径
        output_name = self._output_edit.text().strip() or "merged_output.csv"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出合并 CSV",
            str(self._folder / output_name),
            "CSV 文件 (*.csv)",
        )
        if not save_path:
            return

        # 如果之前已预览，直接复用结果（除非参数变了）
        try:
            df = merge_files(
                filepaths,
                [self._file_states[fn] for fn in self._filenames],
                time_cols,
                freq,
            )
        except Exception as exc:
            QMessageBox.warning(self, "合并失败", str(exc))
            return

        try:
            df.to_csv(save_path, index_label="time")
            self._merged_df = df

            # 自动保存版本
            try:
                self._version_store.create_version(
                    source_files=list(self._filenames),
                    config=self._file_states,
                    csv_path=save_path,
                )
            except Exception:
                pass  # 版本保存失败不影响导出

            QMessageBox.information(
                self,
                "导出成功",
                f"已导出到:\n{save_path}\n共 {len(df)} 行，{len(df.columns)} 列。",
            )
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def _show_preview(self, df: pd.DataFrame) -> None:
        """在预览表格中显示 DataFrame。"""
        self._preview_table.clear()
        self._preview_table.setRowCount(len(df))
        self._preview_table.setColumnCount(len(df.columns) + 1)

        # 表头（第一列是时间）
        headers = ["时间"] + list(df.columns)
        self._preview_table.setHorizontalHeaderLabels(headers)

        for r, (idx, row) in enumerate(df.iterrows()):
            time_item = QTableWidgetItem(str(idx))
            time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._preview_table.setItem(r, 0, time_item)
            for c, val in enumerate(row):
                text = "" if pd.isna(val) else str(val)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._preview_table.setItem(r, c + 1, item)
