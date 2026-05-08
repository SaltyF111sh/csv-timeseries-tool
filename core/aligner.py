"""时间列识别、频率检测、多文件时间对齐合并。"""

from collections import Counter
from pathlib import Path

import pandas as pd

from .csv_handler import ColumnState

TIME_KEYWORDS = ["time", "date", "datetime", "timestamp", "时间", "日期", "时刻"]


def detect_time_column(df: pd.DataFrame) -> str | None:
    """自动识别 DataFrame 中的时间列。

    策略：先按列名关键词匹配，再尝试 pd.to_datetime 解析。
    """
    # 1. 关键词匹配（列名含时间相关词汇）
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in TIME_KEYWORDS):
            return col

    # 2. 值解析尝试（取前20个非空值试转 datetime）
    for col in df.columns:
        sample = df[col].dropna()
        if len(sample) == 0:
            continue
        try:
            pd.to_datetime(sample.head(20))
            return col
        except (ValueError, TypeError):
            continue

    return None


def get_time_range(df: pd.DataFrame, time_col: str) -> tuple[str, str]:
    """返回时间列的范围字符串 (min, max)。"""
    times = pd.to_datetime(df[time_col], errors="coerce").dropna()
    if len(times) == 0:
        return ("N/A", "N/A")
    return (str(times.min()), str(times.max()))


def detect_freq(series: pd.Series) -> str:
    """检测时间序列频率，返回 pandas freq 字符串（如 '1H'、'15T'、'1D'）。"""
    times = pd.to_datetime(series).dropna().sort_values()
    if len(times) < 2:
        return "1D"

    # 优先用 pandas 内置推断
    try:
        freq = pd.infer_freq(times)
        if freq:
            return freq
    except Exception:
        pass

    # 回退：取相邻时间差的众数
    diffs = times.diff().dropna()
    mode_val = diffs.mode()
    if len(mode_val) > 0:
        secs = mode_val.iloc[0].total_seconds()
        return _seconds_to_freq(secs)

    return "1D"


def _seconds_to_freq(secs: float) -> str:
    secs = abs(secs)
    if secs < 60:
        return f"{int(secs)}s"
    elif secs < 3600:
        m = int(secs / 60)
        return f"{m}min" if m > 1 else "1min"
    elif secs < 86400:
        h = int(secs / 3600)
        return f"{h}H" if h > 1 else "1H"
    else:
        d = int(secs / 86400)
        return f"{d}D" if d > 1 else "1D"


def load_file_for_alignment(
    filepath: Path, states: list[ColumnState], time_col: str
) -> pd.DataFrame:
    """读取单个 CSV 文件：只保留勾选列 + 时间列，应用重命名，时间列转 datetime 并设为 index。

    Returns:
        以 datetime 为 index 的 DataFrame（只含勾选的非时间列，列名已重命名）。
    """
    df = pd.read_csv(filepath)

    # 确保时间列存在
    if time_col not in df.columns:
        raise ValueError(f"文件 {filepath.name} 中不存在列「{time_col}」")

    # 收集需要保留的列：勾选的列 + 时间列（防止用户未勾选时间列）
    checked_cols: list[str] = [s.original for s in states if s.checked]
    keep_cols = list(dict.fromkeys([time_col] + checked_cols))  # 去重保序

    df = df[keep_cols].copy()

    # 应用重命名（去重：同一目标名只保留首次出现的列）
    rename_map: dict[str, str] = {}
    seen_renamed: set[str] = set()
    for s in states:
        if s.original not in keep_cols:
            continue
        new_name = s.alias or s.original
        if new_name in seen_renamed:
            # 重名列：跳过，不保留
            keep_cols.remove(s.original)
            continue
        rename_map[s.original] = new_name
        seen_renamed.add(new_name)
    df = df[keep_cols].copy() if keep_cols != df.columns.tolist() else df
    df = df.rename(columns=rename_map)

    # 时间列转 datetime 并设为 index
    time_col_renamed = rename_map.get(time_col, time_col)
    df[time_col_renamed] = pd.to_datetime(df[time_col_renamed], errors="coerce")
    df = df.set_index(time_col_renamed).sort_index()
    # 去除重复时间戳（保留首次出现），避免下游 reindex 报错
    df = df[~df.index.duplicated(keep="first")]

    return df


def merge_files(
    filepaths: list[Path],
    all_states: list[list[ColumnState]],
    time_cols: list[str],
    freq: str,
) -> pd.DataFrame:
    """时间对齐合并多个 CSV 文件。

    Args:
        filepaths: 各文件的完整路径
        all_states: 对应文件的列状态列表
        time_cols: 对应文件的时间列名（原始名）
        freq: pandas 频率字符串

    Returns:
        合并后的 DataFrame，index 为 datetime，列来自各文件的重命名列。
    """
    if len(filepaths) < 2:
        raise ValueError("至少需要2个文件才能进行时间对齐合并")

    # 1. 加载每个文件为以时间为 index 的 DataFrame
    dfs: list[pd.DataFrame] = []
    for fp, states, tc in zip(filepaths, all_states, time_cols):
        df = load_file_for_alignment(fp, states, tc)
        dfs.append(df)

    # 2. 计算时间交集
    min_time = max(df.index.min() for df in dfs)
    max_time = min(df.index.max() for df in dfs)

    if min_time >= max_time:
        raise ValueError("各文件的时间范围无交集，无法合并")

    # 3. 生成统一时间轴
    common_index = pd.date_range(start=min_time, end=max_time, freq=freq)

    # 4. 各文件重排到统一时间轴
    aligned: list[pd.DataFrame] = []
    for i, df in enumerate(dfs):
        # reindex 到统一时间轴，缺失填 NaN
        reindexed = df.reindex(common_index)
        # 添加文件名前缀避免列名冲突
        reindexed.columns = [
            f"{col}" for col in reindexed.columns
        ]
        aligned.append(reindexed)

    # 5. 水平拼接
    result = pd.concat(aligned, axis=1)

    # 6. 跨文件列名去重：同名列只保留首次出现的
    result = result.loc[:, ~result.columns.duplicated()]

    # 7. 按时间排序
    result = result.sort_index()

    return result


def compute_intersection_info(
    filepaths: list[Path],
    all_states: list[list[ColumnState]],
    time_cols: list[str],
) -> tuple[str, str, int] | None:
    """计算时间交集信息，不执行完整合并。

    Returns:
        (min_time, max_time, 交集数据行数) 或 None（无交集）。
    """
    dfs: list[pd.DataFrame] = []
    for fp, states, tc in zip(filepaths, all_states, time_cols):
        df = load_file_for_alignment(fp, states, tc)
        dfs.append(df)

    min_time = max(df.index.min() for df in dfs)
    max_time = min(df.index.max() for df in dfs)

    if min_time >= max_time:
        return None

    # 用最小的频率估算行数（近似值）
    min_freq = None
    for df in dfs:
        if len(df.index) < 2:
            continue
        diff = (df.index.max() - df.index.min()) / len(df.index)
        if min_freq is None or diff < min_freq:
            min_freq = diff

    if min_freq:
        rows = int((max_time - min_time) / min_freq)
    else:
        rows = 0

    return (str(min_time), str(max_time), rows)
