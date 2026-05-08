from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.csv_handler import ColumnState, CsvHandler
from core.version_store import VersionStore
from ui.settings_dialog import SettingsDialog
from ui.time_align_dialog import TimeAlignDialog
from ui.version_panel import VersionPanel

# ---------- 样式常量 ----------
STYLE_SHEET = """
QMainWindow {
    background-color: #f5f6fa;
}
QLabel#folder_path {
    color: #636e72;
    font-size: 12px;
    padding: 4px 8px;
    background: #dfe6e9;
    border-radius: 4px;
}
QPushButton#btn_open {
    background-color: #0984e3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#btn_open:hover {
    background-color: #0773c5;
}
QPushButton#btn_open:pressed {
    background-color: #065ea8;
}
QPushButton#btn_tool {
    background-color: transparent;
    color: #0984e3;
    border: 1px solid #0984e3;
    border-radius: 3px;
    padding: 3px 10px;
    font-size: 12px;
}
QPushButton#btn_tool:hover {
    background-color: #0984e3;
    color: white;
}
QPushButton#btn_next {
    background-color: #00b894;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#btn_next:hover {
    background-color: #00a381;
}
QPushButton#btn_next:pressed {
    background-color: #008e6e;
}
QListWidget#file_list {
    background: white;
    border: 1px solid #dfe6e9;
    border-radius: 4px;
    font-size: 13px;
    outline: none;
}
QListWidget#file_list::item {
    padding: 6px 10px;
    border-bottom: 1px solid #f0f0f0;
}
QListWidget#file_list::item:selected {
    background-color: #74b9ff;
    color: white;
}
QListWidget#file_list::item:hover {
    background-color: #dfe6e9;
}
QListWidget#column_list {
    background: white;
    border: 1px solid #dfe6e9;
    border-radius: 4px;
    outline: none;
}
QListWidget#column_list::item {
    border-bottom: 1px solid #f0f0f0;
}
QListWidget#column_list::item:selected {
    background-color: #dfe6e9;
    color: #2d3436;
}
QTableWidget {
    background: white;
    border: 1px solid #dfe6e9;
    border-radius: 4px;
    gridline-color: #dfe6e9;
    font-size: 13px;
    outline: none;
}
QTableWidget::item {
    padding: 4px 8px;
}
QHeaderView::section {
    background-color: #2d3436;
    color: white;
    padding: 6px 8px;
    border: none;
    font-weight: bold;
    font-size: 13px;
}
QSplitter::handle {
    background-color: #dfe6e9;
    width: 2px;
}
QLabel#section_title {
    font-size: 14px;
    font-weight: bold;
    color: #2d3436;
    margin-bottom: 4px;
}
QLabel#summary_label {
    color: #636e72;
    font-size: 13px;
    padding: 2px 8px;
}
QFrame#bottom_separator {
    background-color: #dfe6e9;
    max-height: 1px;
}
"""

# 自定义数据角色：存储列名
ROLE_COL_NAME = Qt.ItemDataRole.UserRole


# ---------- 列行自定义控件 ----------

class ColumnRowWidget(QWidget):
    """单列编辑行：复选框 + 原名标签 + 重命名输入框。"""

    toggled = pyqtSignal(str, bool)  # col_name, checked
    alias_changed = pyqtSignal(str, str)  # col_name, new_alias

    def __init__(
        self, col_name: str, alias: str, checked: bool, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._col_name = col_name
        self._init_ui(alias, checked)
        self._connect_signals()

    def _init_ui(self, alias: str, checked: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(checked)
        layout.addWidget(self._checkbox)

        self._label = QLabel(self._col_name)
        self._label.setFixedWidth(140)
        self._label.setStyleSheet(
            "color: #2d3436; font-size: 13px; font-weight: bold;"
        )
        layout.addWidget(self._label)

        self._alias_edit = QLineEdit(alias)
        self._alias_edit.setPlaceholderText("重命名（留空=使用原名）")
        self._alias_edit.setStyleSheet(
            "border: 1px solid #dfe6e9; border-radius: 3px; padding: 4px 6px;"
            "font-size: 12px; background: #fff;"
        )
        layout.addWidget(self._alias_edit, stretch=1)

    def _connect_signals(self) -> None:
        self._checkbox.toggled.connect(self._on_toggled)
        self._alias_edit.textChanged.connect(self._on_alias_changed)

    # ---- 公开接口 ----

    def col_name(self) -> str:
        return self._col_name

    def is_checked(self) -> bool:
        return self._checkbox.isChecked()

    def alias(self) -> str:
        return self._alias_edit.text().strip() or self._col_name

    def set_checked(self, checked: bool) -> None:
        self._checkbox.blockSignals(True)
        self._checkbox.setChecked(checked)
        self._checkbox.blockSignals(False)

    def set_alias(self, alias: str) -> None:
        self._alias_edit.blockSignals(True)
        self._alias_edit.setText(alias)
        self._alias_edit.blockSignals(False)

    def mark_matched(self) -> None:
        """将输入框标蓝，表示列名由映射规则自动匹配。"""
        self._alias_edit.setStyleSheet(
            "border: 1px solid #0984e3; border-radius: 3px; padding: 4px 6px;"
            "font-size: 12px; background: #e8f4fd; color: #0984e3; font-weight: bold;"
        )

    # ---- 内部信号 ----

    def _on_toggled(self, checked: bool) -> None:
        self.toggled.emit(self._col_name, checked)

    def _on_alias_changed(self, text: str) -> None:
        self.alias_changed.emit(self._col_name, text.strip())


# ---------- 主窗口 ----------

class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._handler = CsvHandler()
        self._config = ConfigManager.instance()
        self._version_store = VersionStore()
        self._init_ui()
        self._connect_signals()

    # ======== UI 初始化 ========

    def _init_ui(self) -> None:
        self.setWindowTitle("CSV 时间序列整理工具")
        self.resize(1200, 700)
        self.setStyleSheet(STYLE_SHEET)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 4, 12, 0)
        root_layout.setSpacing(0)

        # 顶栏（设置按钮）
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 2, 0, 2)
        top_bar.addStretch()
        self._btn_settings = QPushButton("⚙ 设置")
        self._btn_settings.setStyleSheet(
            "background: transparent; color: #636e72; border: 1px solid #dfe6e9;"
            "border-radius: 3px; padding: 4px 12px; font-size: 12px;"
        )
        top_bar.addWidget(self._btn_settings)
        root_layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._create_left_panel())
        splitter.addWidget(self._create_right_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root_layout.addWidget(splitter, stretch=1)

        # 底部操作栏
        root_layout.addWidget(self._create_bottom_bar())

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 4, 8)
        layout.setSpacing(8)

        title = QLabel("📁 文件列表")
        title.setObjectName("section_title")
        layout.addWidget(title)

        self._btn_open = QPushButton("打开文件夹")
        self._btn_open.setObjectName("btn_open")
        layout.addWidget(self._btn_open)

        self._label_path = QLabel("未选择文件夹")
        self._label_path.setObjectName("folder_path")
        self._label_path.setWordWrap(True)
        layout.addWidget(self._label_path)

        self._file_list = QListWidget()
        self._file_list.setObjectName("file_list")
        layout.addWidget(self._file_list, stretch=1)

        # 历史版本面板（可折叠）
        self._version_panel = VersionPanel(self._version_store)
        layout.addWidget(self._version_panel)

        return panel

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 8, 8, 8)
        layout.setSpacing(8)

        # ---- 列名区域 ----
        col_title = QLabel("📋 列名（勾选 + 拖拽排序 + 重命名）")
        col_title.setObjectName("section_title")
        layout.addWidget(col_title)

        # 工具栏
        toolbar = self._create_column_toolbar()
        layout.addLayout(toolbar)

        # 列名列表（可拖拽）
        self._column_list = QListWidget()
        self._column_list.setObjectName("column_list")
        self._column_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self._column_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._column_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        layout.addWidget(self._column_list)

        # ---- 数据预览区域 ----
        self._label_preview_title = QLabel("📊 数据预览（前5行）")
        self._label_preview_title.setObjectName("section_title")
        layout.addWidget(self._label_preview_title)

        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        # 根据内容自动调整列宽，列数过多时出现水平滚动条
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setMinimumSectionSize(60)
        self._table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        layout.addWidget(self._table)

        return panel

    def _create_column_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(6)

        self._btn_select_all = QPushButton("全选")
        self._btn_select_all.setObjectName("btn_tool")

        self._btn_deselect_all = QPushButton("全不选")
        self._btn_deselect_all.setObjectName("btn_tool")

        self._label_selected_count = QLabel("")
        self._label_selected_count.setStyleSheet(
            "color: #636e72; font-size: 12px;"
        )

        layout.addWidget(self._btn_select_all)
        layout.addWidget(self._btn_deselect_all)
        layout.addWidget(self._label_selected_count)
        layout.addStretch()
        return layout

    def _create_bottom_bar(self) -> QWidget:
        bar = QWidget()
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sep = QFrame()
        sep.setObjectName("bottom_separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(12, 6, 12, 8)

        self._label_summary = QLabel("未选择文件夹")
        self._label_summary.setObjectName("summary_label")
        content_layout.addWidget(self._label_summary, stretch=1)

        self._btn_next = QPushButton("下一步：时间对齐 →")
        self._btn_next.setObjectName("btn_next")
        content_layout.addWidget(self._btn_next)

        layout.addWidget(content)
        return bar

    # ======== 信号连接 ========

    def _connect_signals(self) -> None:
        self._btn_open.clicked.connect(self._on_open_folder)
        self._file_list.itemClicked.connect(self._on_file_selected)
        self._btn_select_all.clicked.connect(self._on_select_all)
        self._btn_deselect_all.clicked.connect(self._on_deselect_all)
        self._btn_next.clicked.connect(self._on_next_step)
        self._btn_settings.clicked.connect(self._on_open_settings)
        # 监听拖拽排序后的 model 变化
        self._column_list.model().rowsMoved.connect(self._on_columns_reordered)
        # 版本回退
        self._version_panel.restore_requested.connect(self._on_restore_config)

    # ======== 事件处理 ========

    def _on_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if not folder:
            return

        try:
            files = self._handler.set_folder(folder)
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "错误", str(exc))
            return

        self._label_path.setText(str(self._handler.folder))

        self._file_list.clear()
        for f in files:
            self._file_list.addItem(QListWidgetItem(f))

        self._clear_preview()
        self._clear_column_list()
        self._update_summary()

    def _on_file_selected(self, item: QListWidgetItem) -> None:
        filename = item.text()

        # 1. 保存当前文件的列状态
        self._persist_current_states()

        # 2. 加载新文件
        try:
            columns, rows = self._handler.load_csv_preview(filename)
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", f"无法读取 {filename}:\n{exc}")
            return

        # 3. 获取/初始化列状态
        states = self._handler.get_column_states(filename, columns)
        # 如果列数变了，重新初始化（文件内容可能已更新）
        if len(states) != len(columns):
            states = self._handler.get_column_states(filename, columns)

        # 3.5 应用列名映射规则（仅对未自定义的列）
        matched_originals: set[str] = set()
        for s in states:
            if s.alias == s.original:
                matched = self._config.match_column(s.original)
                if matched:
                    s.alias = matched
                    matched_originals.add(s.original)

        # 3.6 去重：不同原名映射到相同目标名时，仅保留第一个勾选
        seen_aliases: dict[str, int] = {}
        for i, s in enumerate(states):
            alias = s.alias
            if alias in seen_aliases:
                s.checked = False
            else:
                seen_aliases[alias] = i

        # 4. 重建列列表 UI
        self._rebuild_column_list(states, matched_originals)

        # 5. 刷新数据预览
        self._table.setColumnCount(len(columns))
        self._table.setRowCount(len(rows))
        self._table.setHorizontalHeaderLabels(columns)

        for r, row_data in enumerate(rows):
            for c, value in enumerate(row_data):
                self._table.setItem(r, c, QTableWidgetItem(value))

        self._label_preview_title.setText(
            f"📊 数据预览（{filename}，前{len(rows)}行）"
        )

        # 6. 更新底部汇总
        self._update_summary()

    def _on_select_all(self) -> None:
        self._set_all_checked(True)

    def _on_deselect_all(self) -> None:
        self._set_all_checked(False)

    def _on_open_settings(self) -> None:
        """打开设置对话框，处理后续逻辑。"""
        old_data_dir = self._config.data_dir
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data_dir = self._config.data_dir
            if old_data_dir != new_data_dir:
                self._version_store = VersionStore()
                self._version_panel.set_store(self._version_store)
            # 刷新预览行数标签
            self._label_preview_title.setText(
                f"📊 数据预览（前{self._config.get('preview_rows', 5)}行）"
            )

    def _set_all_checked(self, checked: bool) -> None:
        for i in range(self._column_list.count()):
            widget = self._column_list.itemWidget(
                self._column_list.item(i)
            )
            if isinstance(widget, ColumnRowWidget):
                widget.set_checked(checked)
        self._persist_current_states()
        self._update_summary()
        self._update_selected_count_label()

    def _on_columns_reordered(
        self, parent, start: int, end: int, dest, row: int
    ) -> None:
        """拖拽排序后同步 order 字段。"""
        self._persist_current_states()
        self._update_summary()

    def _on_next_step(self) -> None:
        folder = self._handler.folder
        if folder is None:
            QMessageBox.warning(self, "提示", "请先打开文件夹并加载 CSV 文件。")
            return

        # 收集所有文件的列状态
        file_states: dict[str, list[ColumnState]] = {}
        for i in range(self._file_list.count()):
            filename = self._file_list.item(i).text()
            # 先保存当前 UI 状态
            if filename == self._handler.current_filename():
                self._persist_current_states()
            file_states[filename] = self._handler.get_column_states(filename)

        if len(file_states) < 2:
            QMessageBox.warning(
                self, "提示", "需要至少2个 CSV 文件才能进行时间对齐合并。"
            )
            return

        # 过滤掉没有勾选任何列的文件
        empty_files = [
            fn for fn, states in file_states.items()
            if sum(1 for s in states if s.checked) == 0
        ]
        if empty_files:
            reply = QMessageBox.question(
                self,
                "确认",
                f"以下文件没有勾选任何列，将被排除：\n{chr(10).join(empty_files)}\n\n继续打开时间对齐对话框吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            for fn in empty_files:
                del file_states[fn]

        if len(file_states) < 2:
            QMessageBox.warning(
                self, "提示", "勾选列的文件不足2个，无法进行时间对齐合并。"
            )
            return

        dialog = TimeAlignDialog(folder, file_states, self._version_store, self)
        dialog.exec()
        # 对话框关闭后刷新版本列表（可能有新增版本）
        self._version_panel.refresh()

    def _on_column_toggled(self, col_name: str, checked: bool) -> None:
        self._persist_current_states()
        self._update_summary()
        self._update_selected_count_label()

    def _on_column_alias_changed(self, col_name: str, alias: str) -> None:
        self._persist_current_states()

    # ======== 状态持久化 ========

    def _persist_current_states(self) -> None:
        """将当前列列表 UI 的状态写回 handler。"""
        filename = self._handler.current_filename()
        if filename is None or self._column_list.count() == 0:
            return

        states: list[ColumnState] = []
        for i in range(self._column_list.count()):
            item = self._column_list.item(i)
            widget = self._column_list.itemWidget(item)
            if not isinstance(widget, ColumnRowWidget):
                continue
            states.append(
                ColumnState(
                    original=widget.col_name(),
                    alias=widget.alias(),
                    checked=widget.is_checked(),
                    order=i,
                )
            )

        if states:
            self._handler.save_column_states(filename, states)

    # ======== UI 重建 ========

    def _rebuild_column_list(
        self, states: list[ColumnState],
        matched_originals: set[str] | None = None,
    ) -> None:
        """根据 ColumnState 列表重建列名列表 UI。"""
        if matched_originals is None:
            matched_originals = set()
        self._column_list.clear()

        for state in states:
            row_widget = ColumnRowWidget(
                col_name=state.original,
                alias=state.alias,
                checked=state.checked,
            )
            if state.original in matched_originals:
                row_widget.mark_matched()
            row_widget.toggled.connect(self._on_column_toggled)
            row_widget.alias_changed.connect(self._on_column_alias_changed)

            item = QListWidgetItem()
            item.setData(ROLE_COL_NAME, state.original)
            # 设置高度以容纳自定义控件
            item.setSizeHint(row_widget.sizeHint())
            self._column_list.addItem(item)
            self._column_list.setItemWidget(item, row_widget)

        self._update_selected_count_label()

    def _update_selected_count_label(self) -> None:
        count = self._column_list.count()
        if count == 0:
            self._label_selected_count.setText("")
            return
        selected = sum(
            1
            for i in range(count)
            if isinstance(
                self._column_list.itemWidget(self._column_list.item(i)),
                ColumnRowWidget,
            )
            and self._column_list.itemWidget(
                self._column_list.item(i)
            ).is_checked()
        )
        self._label_selected_count.setText(f"已选 {selected}/{count} 列")

    # ======== 底部汇总 ========

    def _update_summary(self) -> None:
        folder = self._handler.folder
        if folder is None:
            self._label_summary.setText("未选择文件夹")
            return

        total_files = self._file_list.count()
        total_cols = 0
        for i in range(total_files):
            filename = self._file_list.item(i).text()
            total_cols += self._handler.selected_column_count(filename)

        current_file = self._handler.current_filename()
        if current_file:
            file_cols = self._handler.selected_column_count(current_file)
            self._label_summary.setText(
                f"已加载 {total_files} 个文件，共选 {total_cols} 列"
                f"  |  当前文件「{current_file}」已选 {file_cols} 列"
            )
        else:
            self._label_summary.setText(
                f"已加载 {total_files} 个文件，请点击左侧文件查看列详情"
            )

    # ======== 清空 ========

    def _clear_preview(self) -> None:
        self._table.clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._label_preview_title.setText("📊 数据预览（前5行）")

    def _clear_column_list(self) -> None:
        self._column_list.clear()
        self._label_selected_count.setText("")

    # ======== 版本回退 ========

    def _on_restore_config(self, config: dict) -> None:
        """从版本恢复列配置。"""
        restored_count = 0
        for filename, states_dict in config.items():
            states = [ColumnState(**s) for s in states_dict]
            self._handler.save_column_states(filename, states)
            restored_count += 1

        # 刷新当前文件的列列表
        current = self._handler.current_filename()
        if current:
            states = self._handler.get_column_states(current)
            if states:
                self._rebuild_column_list(states)

        self._update_summary()
        QMessageBox.information(
            self, "回退成功", f"已恢复 {restored_count} 个文件的列配置。"
        )
