"""版本管理面板：历史版本列表、详情查看、配置回退、删除。"""

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.version_store import VersionInfo, VersionStore

# ---------- 样式 ----------
PANEL_STYLE = """
QPushButton#version_header {
    text-align: left;
    background: transparent;
    border: none;
    color: #2d3436;
    font-size: 14px;
    font-weight: bold;
    padding: 4px 0;
}
QPushButton#version_header:hover {
    color: #0984e3;
}
QPushButton#version_action {
    background: transparent;
    border-radius: 3px;
    padding: 2px 8px;
    font-size: 11px;
}
QLabel#version_detail {
    color: #636e72;
    font-size: 11px;
    padding: 4px 8px;
    background: #dfe6e9;
    border-radius: 4px;
}
"""


class VersionPanel(QWidget):
    """可折叠的历史版本区域，嵌入主窗口左侧面板。"""

    # 请求将主界面列配置恢复为某版本的配置
    restore_requested = pyqtSignal(dict)  # config: {filename: [ColumnState_dict, ...]}

    def __init__(self, store: VersionStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._selected_id: int | None = None
        self.setStyleSheet(PANEL_STYLE)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # ---- 可折叠标题 ----
        self._header = QPushButton("📋 历史版本 ▼")
        self._header.setObjectName("version_header")
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        # ---- 折叠内容 ----
        self._content = QWidget()
        content = QVBoxLayout(self._content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(4)

        self._list = QListWidget()
        self._list.setMaximumHeight(160)
        self._list.setStyleSheet(
            "background: white; border: 1px solid #dfe6e9; border-radius: 4px;"
            "font-size: 11px; outline: none;"
        )
        self._list.itemClicked.connect(self._on_select)
        self._list.itemDoubleClicked.connect(self._on_edit_note)
        content.addWidget(self._list)

        self._detail = QLabel("点击版本查看详情")
        self._detail.setObjectName("version_detail")
        self._detail.setWordWrap(True)
        content.addWidget(self._detail)

        # 操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self._btn_open = self._make_btn("打开文件", "#0984e3")
        self._btn_open.clicked.connect(self._on_open)
        btn_row.addWidget(self._btn_open)

        self._btn_restore = self._make_btn("回退配置", "#00b894")
        self._btn_restore.clicked.connect(self._on_restore)
        btn_row.addWidget(self._btn_restore)

        self._btn_delete = self._make_btn("删除", "#d63031")
        self._btn_delete.clicked.connect(self._on_delete)
        btn_row.addWidget(self._btn_delete)

        btn_row.addStretch()
        content.addLayout(btn_row)

        layout.addWidget(self._content)

        self._collapsed = False
        self.refresh()

    def _make_btn(self, text: str, color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("version_action")
        btn.setStyleSheet(
            f"QPushButton#version_action {{ color: {color}; border: 1px solid {color}; }}"
            f"QPushButton#version_action:hover {{ background: {color}; color: white; }}"
        )
        return btn

    # ======== 公开 ========

    def set_store(self, store: VersionStore) -> None:
        """更换底层存储（数据目录变更后调用）。"""
        self._store = store
        self._selected_id = None
        self._detail.setText("点击版本查看详情")
        self.refresh()

    def refresh(self) -> None:
        """从数据库重新加载版本列表。"""
        self._list.clear()
        versions = self._store.list_versions()

        for v in versions:
            text = f"{v.name}  |  {v.created_at}  |  {len(v.source_files)}文件"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, v.id)
            self._list.addItem(item)

        if not versions:
            self._list.addItem(QListWidgetItem("（暂无历史版本）"))

    # ======== 折叠 ========

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        arrow = "▶" if self._collapsed else "▼"
        self._header.setText(f"📋 历史版本 {arrow}")

    # ======== 事件 ========

    def _on_select(self, item: QListWidgetItem) -> None:
        vid = item.data(Qt.ItemDataRole.UserRole)
        if vid is None:
            return
        self._selected_id = vid
        self._show_detail(vid)

    def _on_edit_note(self, item: QListWidgetItem) -> None:
        vid = item.data(Qt.ItemDataRole.UserRole)
        if vid is None:
            return
        info = self._store.get_version(vid)
        if info is None:
            return
        note, ok = QInputDialog.getText(
            self, "编辑备注", "输入版本备注:", text=info.note,
        )
        if ok and note != info.note:
            self._store.update_note(vid, note)
            self._show_detail(vid)

    def _on_open(self) -> None:
        info = self._get_selected()
        if info is None:
            return
        path = Path(info.csv_path)
        if not path.is_file():
            QMessageBox.warning(self, "文件不存在", f"快照文件不存在:\n{path}")
            return
        # 系统默认程序打开
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    def _on_restore(self) -> None:
        info = self._get_selected()
        if info is None:
            return
        reply = QMessageBox.question(
            self,
            "确认回退",
            f"将主界面列配置恢复到版本「{info.name}」的状态？\n"
            f"注意：请确保已打开相同的文件夹和文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.restore_requested.emit(info.config)

    def _on_delete(self) -> None:
        info = self._get_selected()
        if info is None:
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除版本「{info.name}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._store.delete_version(info.id)
        self._selected_id = None
        self._detail.setText("点击版本查看详情")
        self.refresh()

    # ======== 内部 ========

    def _get_selected(self) -> VersionInfo | None:
        if self._selected_id is None:
            return None
        return self._store.get_version(self._selected_id)

    def _show_detail(self, vid: int) -> None:
        info = self._store.get_version(vid)
        if info is None:
            return
        files = "\n".join(f"  • {f}" for f in info.source_files)
        self._detail.setText(
            f"名称: {info.name}\n"
            f"时间: {info.created_at}\n"
            f"备注: {info.note or '(无)'}\n"
            f"来源文件 ({len(info.source_files)}):\n{files}"
        )
