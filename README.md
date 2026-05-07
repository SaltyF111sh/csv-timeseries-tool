# CSV 时间序列整理工具

基于 PyQt6 的桌面工具，用于浏览、编辑和合并多个 CSV 文件，支持时间对齐、列管理、版本快照。

## 功能概览

| 模块 | 说明 |
|------|------|
| **文件夹浏览** | 打开文件夹，列出所有 `.csv` 文件，点击即可预览内容 |
| **列管理** | 勾选/取消列、拖拽排序、自定义重命名（支持列名映射规则自动匹配） |
| **时间对齐合并** | 多文件按时间列取交集，统一频率后合并导出为单文件 |
| **版本控制** | 每次导出自动保存配置快照和 CSV 副本，支持回退到历史版本 |
| **设置页** | 自定义数据存储路径、列名映射规则、预览行数、默认时间频率、去重策略等 |

## 技术栈

- **语言**: Python 3.11
- **GUI**: PyQt6 6.5+
- **数据处理**: pandas 2.0+
- **存储**: sqlite3（版本记录）、JSON（配置持久化）

## 项目结构

```
csv-tool/
├── main.py              # 应用入口
├── core/
│   ├── csv_handler.py   # CSV 读写、列状态管理
│   ├── aligner.py       # 时间列识别、频率检测、多文件合并
│   ├── version_store.py # sqlite3 版本记录、快照文件管理
│   └── config_manager.py# JSON 配置读写（单例）
├── ui/
│   ├── main_window.py   # 主窗口（文件列表、预览、列操作）
│   ├── time_align_dialog.py  # 时间对齐合并对话框
│   ├── version_panel.py      # 版本历史面板
│   └── settings_dialog.py    # 设置对话框
├── requirements.txt
└── README.md
```

## 快速开始

### 环境要求

- Python 3.11+
- pip

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd csv-tool

# 创建虚拟环境（可选）
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包为 exe（Windows）

使用 PyInstaller 打包为单个可执行文件：

```bash
pip install pyinstaller
pyinstaller "CSV时间序列整理工具.spec"
```

打包产物输出在 `dist/` 目录下，双击即可运行（无需安装 Python 环境）。

> `.spec` 文件已配置 `console=False`，打包后为无控制台窗口的 GUI 程序。

## 使用说明

### 基本流程

1. **打开文件夹** — 点击"打开文件夹"，选择包含 CSV 文件的目录
2. **预览数据** — 在文件列表中点击文件，右侧表格显示前 N 行（默认 5 行，可在设置中调整）
3. **管理列** — 勾选需要导出的列，拖拽调整顺序，双击别名列可重命名
4. **时间对齐** — 选中至少 2 个文件 → 点击"时间对齐合并" → 自动识别时间列 → 确认时间交集和频率 → 导出
5. **版本回退** — 在版本面板中查看历史导出，可预览快照、回退配置或删除旧版本

### 列名映射规则

设置页支持配置列名映射表，例如将 `pred`、`Predicted`、`y_pred` 自动映射为 `预测值`，减少手动重命名工作。

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `data_dir` | `data` | 版本数据库和快照存储路径 |
| `max_snapshots` | `50` | 最大保留快照数 |
| `default_freq` | `auto` | 时间对齐默认频率（auto 为自动检测） |
| `duplicate_handling` | `first` | 重复时间戳处理策略 |
| `output_filename_template` | `merged_{date}` | 导出文件名模板 |
| `preview_rows` | `5` | 预览时加载的行数 |

## License

MIT
