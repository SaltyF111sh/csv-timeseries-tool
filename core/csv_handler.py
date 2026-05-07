from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config_manager import ConfigManager


@dataclass
class ColumnState:
    """单个列的选中状态与重命名信息。"""

    original: str
    alias: str = ""
    checked: bool = True
    order: int = 0

    def __post_init__(self) -> None:
        if not self.alias:
            self.alias = self.original


class CsvHandler:
    """CSV 文件读写、文件夹扫描、列状态管理——与 UI 无关。"""

    def __init__(self) -> None:
        self._folder: Path | None = None
        self._current_file: str | None = None  # 存文件名，非完整路径
        self._column_states: dict[str, list[ColumnState]] = {}

    # ---- 文件夹操作 ----

    @property
    def folder(self) -> Path | None:
        return self._folder

    def set_folder(self, folder_path: str) -> list[str]:
        """设置工作文件夹，返回 .csv 文件名列表，同时清空所有列状态。"""
        self._folder = Path(folder_path)
        if not self._folder.is_dir():
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")
        self._current_file = None
        self._column_states.clear()
        return sorted(p.name for p in self._folder.glob("*.csv"))

    # ---- 文件操作 ----

    def current_filename(self) -> str | None:
        return self._current_file

    def _resolve_path(self, filename: str) -> Path:
        if self._folder is None:
            raise RuntimeError("未设置工作文件夹")
        return self._folder / filename

    def load_csv_preview(self, filename: str) -> tuple[list[str], list[list[str]]]:
        """读取指定 CSV 的前 {PREVIEW_ROWS} 行，返回 (列名列表, 数据行列表)。"""
        filepath = self._resolve_path(filename)
        if not filepath.is_file():
            raise FileNotFoundError(f"文件不存在: {filepath}")

        nrows = ConfigManager.instance().get("preview_rows", 5)
        df = pd.read_csv(filepath, nrows=nrows)
        self._current_file = filename

        columns: list[str] = df.columns.tolist()
        rows: list[list[str]] = df.fillna("").astype(str).values.tolist()
        return columns, rows

    # ---- 列状态管理 ----

    def get_column_states(
        self, filename: str, columns: list[str] | None = None
    ) -> list[ColumnState]:
        """获取某文件的列状态；首次访问时用 columns 初始化默认值（全选，别名=原名）。"""
        if filename not in self._column_states and columns is not None:
            self._column_states[filename] = [
                ColumnState(original=c, alias=c, checked=True, order=i)
                for i, c in enumerate(columns)
            ]
        return self._column_states.get(filename, [])

    def save_column_states(self, filename: str, states: list[ColumnState]) -> None:
        self._column_states[filename] = [_clone_state(s) for s in states]

    # ---- 汇总查询 ----

    def selected_column_count(self, filename: str) -> int:
        """返回某文件中勾选的列数。"""
        states = self._column_states.get(filename, [])
        return sum(1 for s in states if s.checked)


def _clone_state(s: ColumnState) -> ColumnState:
    return ColumnState(
        original=s.original, alias=s.alias, checked=s.checked, order=s.order
    )
