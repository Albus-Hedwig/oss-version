---
name: oss-version
description: 检查、升级、管理本地开源组件的版本（rtk / agent-reach / codegraph 等，可扩展）。输出本地版本 vs 最新版本对照表、按需升级、列出已登记组件、添加或编辑组件清单。Use when user says "检查组件版本" / "组件版本对照" / "rtk/codegraph/agent-reach 有没有更新" / "升级 rtk" / "升级 codegraph" / "开源组件版本" / "哪些组件该更新了" / "列出组件清单" / "我装了哪些组件" / "加个组件到清单" / "新增 XXX 到组件管理" / "编辑组件配置", or wants to check/update versions of, or manage the registry of, locally-installed open-source CLI tools managed by this skill.
---

# oss-version：开源组件版本管理

管理 `~/.claude/skills/oss-version/components.toml` 中登记的本地开源 CLI 组件。脚本位置：`scripts/oss-version.py`，用 uv 的 Python 3.12 执行。

## 四个动作

### A. 检查版本

用户问"检查组件版本"、"有没有更新"、"rtk/codegraph/agent-reach 最新版是什么"时：

1. 运行：
   ```bash
   /Users/chenhaoyu/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 ~/.claude/skills/oss-version/scripts/oss-version.py check
   ```
2. 把输出的对照表原样转给用户。
3. `outdated` 的组件进入升级候选；`latest` / `not_installed` / `error` 的跳过并说明原因。

### B. 升级组件

用户说"升级 rtk"、"升级 codegraph"、"全部升级"时：

1. 如果还没跑过 `check`，先跑 `check` 拿到 outdated 列表。
2. **逐个确认**。对每个 outdated 组件问用户："是否升级 `<name>`？命令是 `<upgrade_cmd>`。"
3. 用户确认后，先运行：
   ```bash
   /Users/chenhaoyu/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 ~/.claude/skills/oss-version/scripts/oss-version.py upgrade <name>
   ```
   获取待执行的升级命令。
4. 用 Bash 执行打印出的 `upgrade_cmd`。
5. 执行完成后，重新运行 `check` 验证该组件版本已更新。
6. 重复直到用户不再升级。

### C. 列出组件

用户问"列出组件清单"、"我装了哪些组件"时：

1. 运行：
   ```bash
   /Users/chenhaoyu/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 ~/.claude/skills/oss-version/scripts/oss-version.py list
   ```
2. 把清单转给用户。
3. 附提示："要查版本用 `check`，要加组件告诉我'加个 XXX'。"

### D. 添加 / 编辑组件

用户说"加个组件到清单"、"新增 XXX 到组件管理"、"编辑 rtk 配置"时：

1. **收集信息**，必须问清：
   - `name`：组件唯一标识（如 `mytool`）
   - `binary`：可执行文件名（如 `mytool`）
   - `local_cmd`：拿本地版本号的命令（如 `mytool --version`）
   - `local_regex`：从命令输出提取版本号的正则（第一个捕获组，如 `(\d+\.\d+\.\d+)`）
   - `latest` 来源类型和参数：
     - GitHub releases → `github_release`，需要 `repo`（如 `org/repo`）和可选 `tag_prefix`
     - 工具自带检查命令 → `builtin_check`，需要 `cmd` 和 `regex`
     - GitHub raw 文件 → `github_raw`，需要 `repo`、`branch`、`file`、`regex`
     - PyPI → `pypi`，需要 `package`
     - crates.io → `crates`，需要 `crate`
   - `upgrade_cmd`：升级要执行的命令
   - `upgrade_note`：升级命令的说明（可选）

2. **修改 `components.toml`**：
   - 新增：用 Edit/Write 在文件末尾追加一段 `[[component]]`。
   - 编辑：先 Read 文件定位该组件那一段，用 Edit 精确替换，不动其他组件。

3. **立即验证**：修改后运行 `check`，只看该组件是否正确解析出本地和最新版本。解析失败则回头调整 `local_regex` / `latest.regex` / 来源字段。

4. 告诉用户："`<name>` 已加入清单，之后 `check` 会自动覆盖它。"

## 关键约束

- 脚本路径和 Python 解释器必须写死：
  ```bash
  /Users/chenhaoyu/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 ~/.claude/skills/oss-version/scripts/oss-version.py
  ```
  不要依赖系统 `python3`（默认是 3.9.6，无 `tomllib`）。
- `upgrade` 子命令只打印命令，**不自动执行**。必须由用户在确认后，由 Claude 用 Bash 执行。
- 编辑 `components.toml` 时只改目标组件那一段，保留其他组件。
- 不管未登记的组件；用户要新增时走"添加组件"流程。
- `oss-version.py` 优先用标准库 `urllib` 请求 GitHub；若 uv Python 对 `raw.githubusercontent.com` SSL 握手失败，会自动回退到 `curl`。
