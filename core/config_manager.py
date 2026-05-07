"""配置管理器：JSON 文件读写，单例模式。"""

import json
import sys
from pathlib import Path
from typing import Any

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent

CONFIG_PATH = BASE_DIR / "data" / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "data_dir": "data",
    "max_snapshots": 50,
    "default_freq": "auto",
    "duplicate_handling": "first",
    "output_filename_template": "merged_{date}",
    "preview_rows": 5,
    "column_mappings": {
        "pred": ["pred", "Pred", "predicted", "y_pred", "forecast"],
        "actual": ["true", "actual", "Actual", "y_true", "real", "label"],
        "time": ["time", "Time", "datetime", "DATE", "timestamp", "ds"],
    },
}


class ConfigManager:
    """应用配置单例。"""

    _instance: "ConfigManager | None" = None

    def __init__(self) -> None:
        if ConfigManager._instance is not None:
            return
        ConfigManager._instance = self
        self._config: dict[str, Any] = {}
        self._load()

    @classmethod
    def instance(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---- 读写 ----

    def _load(self) -> None:
        self._config = dict(DEFAULT_CONFIG)
        if CONFIG_PATH.is_file():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._config.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def update(self, data: dict[str, Any]) -> None:
        self._config.update(data)

    @property
    def data_dir(self) -> Path:
        d = self._config.get("data_dir", "data")
        path = Path(d)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    # ---- 列名映射 ----

    def match_column(self, col_name: str) -> str | None:
        """大小写敏感匹配列名映射规则，命中则返回目标名。"""
        mappings: dict[str, list[str]] = self._config.get("column_mappings", {})
        for target, aliases in mappings.items():
            for alias in aliases:
                if alias == col_name:
                    return target
        return None
