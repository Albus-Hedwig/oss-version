# oss-version

A generic version manager for locally-installed open-source CLI tools.

It works with any tool you can describe:

- How to get the **local version** (`mytool --version` + regex)
- How to get the **latest version** (GitHub release, GitHub raw file, PyPI, crates.io, npm, Homebrew, built-in checker, ...)
- How to **upgrade** it (`curl ... | sh`, `brew upgrade`, `cargo install`, etc.)

Ships with presets for common dev tools, but the registry is entirely user-controlled.

## Quick start (as a Claude Code skill)

Install into `~/.claude/skills/oss-version/` and say:

- `"检查组件版本"` — check all registered tools
- `"列出组件清单"` — list registered tools
- `"升级 rtk"` — upgrade one tool
- `"加个组件到清单"` — add a new tool
- `"导入 dev-tools preset"` — import a preset

## Standalone usage

```bash
# Install
uv tool install git+https://github.com/Albus-Hedwig/oss-version.git

# Or clone and run directly
python3.12 scripts/oss-version.py check
```

## Configuration

Edit `components.toml`:

```toml
[[component]]
name = "mytool"
desc = "My CLI tool"
binary = "mytool"
local_cmd = "mytool --version"
local_regex = '(\d+\.\d+\.\d+)'
upgrade_cmd = "curl -fsSL https://example.com/install.sh | sh"

[component.latest]
type = "github_release"
repo = "owner/repo"
tag_prefix = "v"
```

Supported `latest.type` values:

| Type | Fields | Source |
|------|--------|--------|
| `github_release` | `repo`, `tag_prefix` | GitHub releases API |
| `github_tag` | `repo`, `tag_prefix` | GitHub tags API |
| `github_raw` | `repo`, `branch`, `file`, `regex` | Raw file on GitHub |
| `builtin_check` | `cmd`, `regex` | Tool's own version-check command |
| `pypi` | `package` | PyPI JSON API |
| `crates` | `crate` | crates.io API |
| `npm` | `package` | npm registry |
| `homebrew` | `formula` | `brew info` |

## Presets

See `presets/` for starter registries:

- `dev-tools.toml` — common CLI dev tools
- `python-dev.toml` — Python toolchain
- `rust-dev.toml` — Rust toolchain

Import a preset:

```bash
oss-version preset import presets/dev-tools.toml
```

## Discover

Scan PATH for known tools and generate candidate entries:

```bash
oss-version discover
```

## Repository structure

```
├── SKILL.md              # Claude Code skill manifest
├── README.md             # This file
├── components.toml       # Your local registry (user-editable)
├── examples/             # Example registries
├── presets/              # Starter registries
├── pyproject.toml        # Python package metadata
└── scripts/oss-version.py # Core implementation
```
