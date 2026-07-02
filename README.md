# oss-version

A generic version manager for locally-installed open-source CLI tools.

## Install

```bash
# Via uv (recommended)
uv tool install git+https://github.com/Albus-Hedwig/oss-version.git

# Via pip
pipx install git+https://github.com/Albus-Hedwig/oss-version.git

# Or clone and run directly
python3.12 -m oss_version check
```

## Quick start

```bash
oss-version check          # check registered tools
oss-version list           # list registered tools
oss-version upgrade rtk    # show upgrade command for rtk
oss-version preset list    # list available presets
oss-version preset import dev-tools   # import a preset
oss-version discover       # discover known tools in PATH
```

## Configuration

Edit `components.toml` in the config directory (default: `~/.claude/skills/oss-version/components.toml`, override with `OSS_VERSION_CONFIG`).

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

| Type | Fields |
|------|--------|
| `github_release` | `repo`, `tag_prefix` |
| `github_tag` | `repo`, `tag_prefix` |
| `github_raw` | `repo`, `branch`, `file`, `regex` |
| `builtin_check` | `cmd`, `regex` |
| `pypi` | `package` |
| `crates` | `crate` |
| `npm` | `package` |
| `homebrew` | `formula` |

## Presets

See `presets/` for starter registries:

- `dev-tools.toml`
- `python-dev.toml`
- `rust-dev.toml`
- `go-dev.toml`
- `node-dev.toml`

## Claude Code skill

This repository is also a Claude Code global skill. Copy or symlink it to `~/.claude/skills/oss-version/`.

## License

MIT
