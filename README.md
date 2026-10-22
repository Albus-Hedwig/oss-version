# oss-version

Check installed CLI versions against their upstream sources and print the commands you need to upgrade them.

Define each tool in TOML: its local version command, latest-version source, and upgrade command. Run it as a standalone Python CLI or use the included Claude Code skill.

**Python 3.11+ · Standard-library runtime · User-controlled registry**

## Quick start

From an empty directory, clone the repository and run without installing a package:

```bash
git clone https://github.com/Albus-Hedwig/oss-version.git
cd oss-version
python3 --version  # Must be 3.11 or newer
export OSS_VERSION_CONFIG="$PWD/components.toml"
python3 scripts/oss-version.py --help
python3 scripts/oss-version.py list
```

The starter registry is empty. Add your own entries using the configuration below, or import a preset after reviewing its commands:

```bash
python3 scripts/oss-version.py preset list
python3 scripts/oss-version.py preset import presets/dev-tools.toml
python3 scripts/oss-version.py check
python3 scripts/oss-version.py upgrade rtk
```

`upgrade rtk` prints an upgrade command for review. It does not execute that command.

Prefer an installed CLI? With [uv](https://docs.astral.sh/uv/) available:

```bash
uv tool install git+https://github.com/Albus-Hedwig/oss-version.git
oss-version --help
```

Keep `OSS_VERSION_CONFIG` set to your registry file. Without it, the CLI reads `~/.claude/skills/oss-version/components.toml`; installing the package does not create that file or install presets. Use paths to presets from your clone when importing them.

## See the output

This is actual CLI output from a controlled offline demo. Both versions come from `printf` commands in the demo registry, so it demonstrates the format and command rendering rather than an online update check.

```text
$ oss-version check
COMPONENT  LOCAL  LATEST  STATUS    SOURCE
demo       1.2.3  1.3.0   outdated  builtin_check

Upgrade candidates:
  demo:
    cmd:   echo install-demo-1.3.0

Confirm which component(s) to upgrade.
```

<details>
<summary>Reproduce the offline demo</summary>

From the repository directory, save this as `demo.toml`:

```toml
[[component]]
name = "demo"
local_cmd = "printf 'demo 1.2.3\\n'"
local_regex = '(\d+\.\d+\.\d+)'
upgrade_cmd = "echo install-demo-{version}"

[component.latest]
type = "builtin_check"
cmd = "printf 'latest 1.3.0\\n'"
regex = '(\d+\.\d+\.\d+)'
```

Run it without changing your normal registry:

```bash
OSS_VERSION_CONFIG="$PWD/demo.toml" python3 scripts/oss-version.py check
OSS_VERSION_CONFIG="$PWD/demo.toml" python3 scripts/oss-version.py upgrade demo
```

</details>

## Use with Claude Code

Clone into the skill directory. Use a new target directory; if you already have this skill, preserve its registry before updating it.

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/Albus-Hedwig/oss-version.git ~/.claude/skills/oss-version
python3 --version  # Must be 3.11 or newer
python3 ~/.claude/skills/oss-version/scripts/oss-version.py list
```

Then ask Claude Code:

- `检查组件版本`: compare registered versions.
- `列出组件清单`: list the registry.
- `加个组件到清单`: add a tool.
- `导入 dev-tools preset`: import a starter registry.
- `升级 rtk`: review and confirm an upgrade.

The [skill instructions](SKILL.md) require confirmation before Claude executes each upgrade command. If your system `python3` is older than 3.11, use an available Python 3.11+ interpreter for the skill commands.

## Configure your tools

Edit the registry selected by `OSS_VERSION_CONFIG`, or the default skill registry:

```toml
[[component]]
name = "mytool"
desc = "My CLI tool"
binary = "mytool"
local_cmd = "mytool --version"
local_regex = '(\d+\.\d+\.\d+)'
upgrade_cmd = "brew upgrade mytool"

[component.latest]
type = "github_release"
repo = "owner/repo"
tag_prefix = "v"
```

Replace the example tool, source, and upgrade command with your own. Use the first regex capture group for the version.

`binary` is optional. For GUI apps or Docker-based tools, omit it and let `local_cmd` determine whether the component is installed. For example, a macOS app can use `defaults read "/Applications/CC Switch.app/Contents/Info" CFBundleShortVersionString` as its local version command.

Upgrade commands support these placeholders:

| Placeholder | Value |
| --- | --- |
| `{version}` | Latest version after stripping `tag_prefix`, such as `3.16.5` |
| `{tag}` | Original release tag, such as `v3.16.5`; falls back to the version |
| `{repo}` | Configured repository, such as `owner/repo` |

Supported latest-version sources:

| `latest.type` | Fields | Source |
| --- | --- | --- |
| `github_release` | `repo`, optional `tag_prefix` | Latest GitHub release |
| `github_tag` | `repo`, optional `tag_prefix` | First result from GitHub tags API |
| `github_raw` | `repo`, `file`, `regex`, optional `branch` (default: `main`) | File on GitHub |
| `builtin_check` | `cmd`, `regex` | Tool's version-check command |
| `pypi` | `package` | PyPI |
| `crates` | `crate` | crates.io |
| `npm` | `package` | npm registry |
| `homebrew` | `formula` | `brew info` |

### Presets and discovery

Browse [presets](presets/) for `dev-tools`, `python-dev`, `rust-dev`, `node-dev`, and `go-dev`. See [examples](examples/) for a sample registry. Review install methods for your operating system before importing.

`preset import` appends entries and skips names already in the registry. `preset list` reads a `presets/` directory beside your selected registry.

```bash
oss-version preset import presets/python-dev.toml
oss-version discover
```

`discover` scans PATH for known tools and prints candidate entries. Review and copy the entries you want into your registry.

## Command execution

Treat registries as executable configuration. During `check`, the CLI runs each `local_cmd`; it also runs commands for `builtin_check` and Homebrew sources. Only use configuration and commands you trust.

`check` and `upgrade <name>` print upgrade commands. To apply an upgrade, review the printed command and execute it yourself, or confirm it through the Claude Code skill. Depending on your registry, that command may modify globally installed tools or run an installer script.

Version comparison uses numeric dot-separated parts. Check prerelease and nonnumeric version labels yourself.

## Development

```bash
uv sync --extra dev
uv run pytest -q
```

The implementation lives in [oss_version](oss_version/); [scripts/oss-version.py](scripts/oss-version.py) provides the direct-run skill entry point.

