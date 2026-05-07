"""版本存储：sqlite3 记录导出历史、CSV 快照管理。"""

import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .config_manager import ConfigManager
from .csv_handler import ColumnState


@dataclass
class VersionInfo:
    """版本只读数据。"""

    id: int
    name: str
    created_at: str
    note: str
    source_files: list[str]
    config: dict  # {filename: [ColumnState_as_dict, ...]}
    csv_path: str


class VersionStore:
    """管理 sqlite 版本记录和 CSV 快照文件。"""

    def __init__(self, data_dir: Path | None = None) -> None:
        if data_dir is not None:
            self._data_dir = data_dir
        else:
            self._data_dir = ConfigManager.instance().data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        (self._data_dir / "snapshots").mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "versions.db"
        self._init_db()

    # ======== 数据库初始化 ========

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS versions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    name         TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    note         TEXT DEFAULT '',
                    source_files TEXT NOT NULL,
                    config       TEXT NOT NULL,
                    csv_path     TEXT NOT NULL
                )"""
            )

    # ======== 公开接口 ========

    def create_version(
        self,
        source_files: list[str],
        config: dict[str, list[ColumnState]],
        csv_path: str,
        note: str = "",
    ) -> int:
        """创建版本记录并复制 CSV 快照到 data/snapshots/。

        Returns:
            新版本的 id。
        """
        name = f"版本_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        config_json = json.dumps(
            {
                fn: [asdict(s) for s in states]
                for fn, states in config.items()
            },
            ensure_ascii=False,
        )
        source_json = json.dumps(source_files, ensure_ascii=False)

        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO versions (name, created_at, note, source_files, config, csv_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, created_at, note, source_json, config_json, csv_path),
            )
            version_id = cursor.lastrowid

        # 复制 CSV 快照
        src = Path(csv_path)
        snapshot_path = self._data_dir / "snapshots" / f"v{version_id}_{src.name}"
        shutil.copy2(src, snapshot_path)

        # 更新记录中的 csv_path 为快照路径
        with self._connect() as conn:
            conn.execute(
                "UPDATE versions SET csv_path = ? WHERE id = ?",
                (str(snapshot_path), version_id),
            )

        return version_id

    def list_versions(self) -> list[VersionInfo]:
        """返回所有版本，按创建时间降序。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM versions ORDER BY id DESC"
            ).fetchall()
        return [self._row_to_info(r) for r in rows]

    def get_version(self, version_id: int) -> VersionInfo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM versions WHERE id = ?", (version_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_info(row)

    def update_note(self, version_id: int, note: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE versions SET note = ? WHERE id = ?",
                (note, version_id),
            )

    def delete_version(self, version_id: int) -> None:
        """删除版本记录和对应的快照文件。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT csv_path FROM versions WHERE id = ?", (version_id,)
            ).fetchone()

            if row:
                snapshot_path = Path(row["csv_path"])
                try:
                    if snapshot_path.exists():
                        snapshot_path.unlink()
                except OSError:
                    pass

            conn.execute("DELETE FROM versions WHERE id = ?", (version_id,))

    # ======== 内部 ========

    def _row_to_info(self, row: sqlite3.Row) -> VersionInfo:
        return VersionInfo(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            note=row["note"],
            source_files=json.loads(row["source_files"]),
            config=json.loads(row["config"]),
            csv_path=row["csv_path"],
        )
