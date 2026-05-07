"""设置对话框：存储、数据处理、界面、列名映射规则。"""

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import BASE_DIR, ConfigManager

_STYLE = """
QDialog { background-color: #f5f6fa; }
QGroupBox { font-size: 13px; font-weight: bold; color: #2d3436;
    border: 1px solid #dfe6e9; border-radius: 6px; margin-top: 8px;
    padding-top: 16px; background: #fff; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
QLineEdit, QSpinBox, QComboBox { border: 1px solid #dfe6e9; border-radius: 3px;
    padding: 4px 8px; font-size: 12px; background: white; }
QTableWidget { background: white; border: 1px solid #dfe6e9; border-radius: 4px;
    gridline-color: #dfe6e9; font-size: 12px; outline: none; }
QHeaderView::section { background-color: #2d3436; color: white; padding: 5px 8px;
    border: none; font-weight: bold; font-size: 12px; }
QTabWidget::pane { border: 1px solid #dfe6e9; border-radius: 4px; background: #f5f6fa; }
QTabBar::tab { background: #dfe6e9; color: #2d3436; padding: 6px 16px; margin-right: 2px;
    border-top-left-radius: 4px; border-top-right-radius: 4px; font-size: 13px; }
QTabBar::tab:selected { background: #0984e3; color: white; }
QPushButton#btn_browse { background: transparent; color: #0984e3;
    border: 1px solid #0984e3; border-radius: 3px; padding: 4px 12px; }
QPushButton#btn_browse:hover { background: #0984e3; color: white; }
QPushButton#btn_add { background: transparent; color: #00b894;
    border: 1px solid #00b894; border-radius: 3px; padding: 4px 12px; }
QPushButton#btn_add:hover { background: #00b894; color: white; }
QPushButton#btn_delete { background: transparent; color: #d63031;
    border: 1px solid #d63031; border-radius: 3px; padding: 2px 8px; font-size: 11px; }
QPushButton#btn_delete:hover { background: #d63031; color: white; }
"""


def _field(label: str, w: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    lbl = QLabel(label)
    lbl.setStyleSheet("font-size: 12px; color: #2d3436;")
    lbl.setFixedWidth(120)
    row.addWidget(lbl)
    row.addWidget(w, stretch=1)
    return row


def _hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #b2bec3; font-size: 11px; padding: 2px 0;")
    lbl.setWordWrap(True)
    return lbl


def _action_btn(text: str, obj: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(obj)
    return btn


# ======== 设置对话框 ========


class SettingsDialog(QDialog):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = ConfigManager.instance()
        self._old_data_dir = self._config.data_dir
        self.setStyleSheet(_STYLE)
        self._init_ui()
        self._load_current()

    # ======== UI ========

    def _init_ui(self) -> None:
        self.setWindowTitle("设置")
        self.resize(620, 580)
        self.setMinimumSize(520, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        tabs = QTabWidget()
        tabs.addTab(self._storage_tab(), "存储")
        tabs.addTab(self._process_tab(), "数据处理")
        tabs.addTab(self._ui_tab(), "界面")
        tabs.addTab(self._mappings_tab(), "列名映射")
        root.addWidget(tabs, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = QPushButton("确定")
        ok.setStyleSheet(
            "background:#0984e3;color:white;border:none;padding:6px 16px;"
            "font-weight:bold;border-radius:3px;"
        )
        ok.clicked.connect(self._on_accept)
        cancel = QPushButton("取消")
        cancel.setStyleSheet(
            "background:transparent;color:#636e72;border:1px solid #dfe6e9;"
            "padding:6px 16px;border-radius:3px;"
        )
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        root.addLayout(btn_row)

    # ---- tab: 存储 ----

    def _storage_tab(self) -> QWidget:
        page = QWidget()
        ly = QVBoxLayout(page)
        ly.setContentsMargins(8, 8, 8, 8)
        ly.setSpacing(12)

        g1 = QGroupBox("数据存储位置")
        g1ly = QVBoxLayout(g1)
        pr = QHBoxLayout()
        self._data_dir_edit = QLineEdit()
        self._data_dir_edit.setPlaceholderText("相对路径或绝对路径")
        pr.addWidget(self._data_dir_edit)
        b = _action_btn("浏览", "btn_browse")
        b.clicked.connect(self._on_browse_data_dir)
        pr.addWidget(b)
        g1ly.addLayout(pr)
        g1ly.addWidget(_hint("修改后确认时将提示是否迁移现有数据"))
        ly.addWidget(g1)

        g2 = QGroupBox("快照保留数量上限")
        g2ly = QVBoxLayout(g2)
        self._max_snap = QSpinBox()
        self._max_snap.setRange(1, 9999)
        g2ly.addLayout(_field("最大保留数:", self._max_snap))
        g2ly.addWidget(_hint("超出时最早版本自动清理"))
        ly.addWidget(g2)

        ly.addStretch()
        return page

    # ---- tab: 数据处理 ----

    def _process_tab(self) -> QWidget:
        page = QWidget()
        ly = QVBoxLayout(page)
        ly.setContentsMargins(8, 8, 8, 8)
        ly.setSpacing(12)

        g1 = QGroupBox("默认时间步长")
        g1ly = QVBoxLayout(g1)
        self._freq_combo = QComboBox()
        self._freq_combo.addItems(["自动检测", "1min", "15min", "1H", "1D"])
        g1ly.addLayout(_field("时间步长:", self._freq_combo))
        ly.addWidget(g1)

        g2 = QGroupBox("重复时间戳处理")
        g2ly = QVBoxLayout(g2)
        self._dup_combo = QComboBox()
        self._dup_combo.addItems(["取第一个", "取最后一个", "取均值"])
        g2ly.addLayout(_field("处理方式:", self._dup_combo))
        ly.addWidget(g2)

        g3 = QGroupBox("默认输出文件名模板")
        g3ly = QVBoxLayout(g3)
        self._out_tmpl = QLineEdit()
        self._out_tmpl.setPlaceholderText("merged_{date}")
        g3ly.addLayout(_field("模板:", self._out_tmpl))
        g3ly.addWidget(_hint("{date} 会被替换为当前日期"))
        ly.addWidget(g3)

        ly.addStretch()
        return page

    # ---- tab: 界面 ----

    def _ui_tab(self) -> QWidget:
        page = QWidget()
        ly = QVBoxLayout(page)
        ly.setContentsMargins(8, 8, 8, 8)
        ly.setSpacing(12)

        g1 = QGroupBox("数据预览行数")
        g1ly = QVBoxLayout(g1)
        self._preview_combo = QComboBox()
        self._preview_combo.addItems(["5", "10", "20"])
        g1ly.addLayout(_field("预览行数:", self._preview_combo))
        ly.addWidget(g1)

        ly.addStretch()
        return page

    # ---- tab: 列名映射 ----

    def _mappings_tab(self) -> QWidget:
        page = QWidget()
        ly = QVBoxLayout(page)
        ly.setContentsMargins(8, 8, 8, 8)
        ly.setSpacing(8)

        g1 = QGroupBox("列名映射规则")
        g1ly = QVBoxLayout(g1)

        self._map_table = QTableWidget()
        self._map_table.setColumnCount(3)
        self._map_table.setHorizontalHeaderLabels(["目标列名", "别名（逗号分隔）", "操作"])
        self._map_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._map_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._map_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._map_table.setMinimumHeight(200)
        g1ly.addWidget(self._map_table)

        add_btn = _action_btn("+ 新增规则", "btn_add")
        add_btn.clicked.connect(self._on_add_mapping)
        g1ly.addWidget(add_btn)
        g1ly.addWidget(
            _hint("打开 CSV 时自动匹配列名并预填统一列名（大小写敏感）")
        )

        ly.addWidget(g1)
        ly.addStretch()
        return page

    # ======== 加载 / 保存 ========

    def _load_current(self) -> None:
        self._data_dir_edit.setText(str(self._config.get("data_dir", "data")))
        self._max_snap.setValue(self._config.get("max_snapshots", 50))

        freq_map = {"auto": "自动检测", "1min": "1min", "15min": "15min",
                     "1H": "1H", "1D": "1D"}
        freq_val = self._config.get("default_freq", "auto")
        self._freq_combo.setCurrentText(freq_map.get(freq_val, "自动检测"))

        dup_map = {"first": "取第一个", "last": "取最后一个", "mean": "取均值"}
        dup_val = self._config.get("duplicate_handling", "first")
        self._dup_combo.setCurrentText(dup_map.get(dup_val, "取第一个"))

        self._out_tmpl.setText(
            self._config.get("output_filename_template", "merged_{date}")
        )

        preview_val = str(self._config.get("preview_rows", 5))
        self._preview_combo.setCurrentText(preview_val)

        self._load_mappings()

    def _load_mappings(self) -> None:
        mappings: dict = self._config.get("column_mappings", {})
        self._map_table.setRowCount(0)
        for target, aliases in mappings.items():
            self._add_mapping_row(target, ", ".join(aliases))

    def _add_mapping_row(self, target: str = "", aliases: str = "") -> None:
        r = self._map_table.rowCount()
        self._map_table.insertRow(r)
        self._map_table.setItem(r, 0, QTableWidgetItem(target))
        self._map_table.setItem(r, 1, QTableWidgetItem(aliases))

        del_btn = QPushButton("删除")
        del_btn.setObjectName("btn_delete")
        del_btn.clicked.connect(lambda checked, row=r: self._on_del_mapping(row))
        self._map_table.setCellWidget(r, 2, del_btn)

    def _collect_mappings(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for r in range(self._map_table.rowCount()):
            target_item = self._map_table.item(r, 0)
            alias_item = self._map_table.item(r, 1)
            if not target_item or not alias_item:
                continue
            target = target_item.text().strip()
            aliases_text = alias_item.text().strip()
            if not target or not aliases_text:
                continue
            aliases = [a.strip() for a in aliases_text.split(",") if a.strip()]
            if aliases:
                result[target] = aliases
        return result

    # ======== 事件 ========

    def _on_browse_data_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择数据存储目录")
        if folder:
            self._data_dir_edit.setText(folder)

    def _on_add_mapping(self) -> None:
        self._add_mapping_row()

    def _on_del_mapping(self, row: int) -> None:
        self._map_table.removeRow(row)

    def _on_accept(self) -> None:
        new_data_dir = self._data_dir_edit.text().strip() or "data"
        new_data_path = Path(new_data_dir)
        if not new_data_path.is_absolute():
            new_data_path = BASE_DIR / new_data_path

        # 数据目录变更 → 询问迁移
        old_dir = self._old_data_dir
        if old_dir != new_data_path:
            reply = QMessageBox.question(
                self, "迁移数据",
                f"数据存储位置已更改，是否将现有数据迁移到新位置？\n\n"
                f"旧位置: {old_dir}\n新位置: {new_data_path}\n\n"
                f"选择「否」则使用新位置（数据从零开始）。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._migrate_data(old_dir, new_data_path)
                except Exception as exc:
                    QMessageBox.warning(self, "迁移失败", str(exc))

        # 保存配置
        freq_map_inv = {"自动检测": "auto", "1min": "1min",
                        "15min": "15min", "1H": "1H", "1D": "1D"}
        dup_map_inv = {"取第一个": "first", "取最后一个": "last", "取均值": "mean"}

        self._config.update({
            "data_dir": new_data_dir,
            "max_snapshots": self._max_snap.value(),
            "default_freq": freq_map_inv.get(self._freq_combo.currentText(), "auto"),
            "duplicate_handling": dup_map_inv.get(
                self._dup_combo.currentText(), "first"
            ),
            "output_filename_template": self._out_tmpl.text().strip() or "merged_{date}",
            "preview_rows": int(self._preview_combo.currentText()),
            "column_mappings": self._collect_mappings(),
        })
        self._config.save()
        self.accept()

    def _migrate_data(self, src: Path, dst: Path) -> None:
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "snapshots").mkdir(parents=True, exist_ok=True)

        db_src = src / "versions.db"
        if db_src.is_file():
            shutil.copy2(db_src, dst / "versions.db")

        snap_src = src / "snapshots"
        snap_dst = dst / "snapshots"
        if snap_src.is_dir():
            for f in snap_src.iterdir():
                shutil.copy2(f, snap_dst / f.name)
