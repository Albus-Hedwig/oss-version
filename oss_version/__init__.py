#!/usr/bin/env python3
"""oss-version: check and manage versions of locally-installed open-source CLI tools."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = Path.home() / ".claude" / "skills" / "oss-version" / "components.toml"
CONFIG_PATH = Path(os.environ.get("OSS_VERSION_CONFIG", DEFAULT_CONFIG_PATH))
USER_AGENT = "oss-version-check"


# ---------------------------------------------------------------------------
# Known tool patterns for auto-discovery
# ---------------------------------------------------------------------------

KNOWN_TOOLS: dict[str, dict] = {
    "gh": {
        "desc": "GitHub CLI",
        "local_cmd": "gh --version",
        "local_regex": r"gh\s+version\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "brew upgrade gh",
        "upgrade_note": "Homebrew",
        "latest": {"type": "homebrew", "formula": "gh"},
    },
    "fzf": {
        "desc": "Command-line fuzzy finder",
        "local_cmd": "fzf --version",
        "local_regex": r"(\d+\.\d+\.\d+)",
        "upgrade_cmd": "brew upgrade fzf",
        "upgrade_note": "Homebrew",
        "latest": {"type": "homebrew", "formula": "fzf"},
    },
    "uv": {
        "desc": "Extremely fast Python package installer and resolver",
        "local_cmd": "uv --version",
        "local_regex": r"uv\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "upgrade_note": "uv official install.sh",
        "latest": {"type": "github_release", "repo": "astral-sh/uv", "tag_prefix": ""},
    },
    "rg": {
        "desc": "ripgrep line-oriented search tool",
        "local_cmd": "rg --version",
        "local_regex": r"ripgrep\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "brew upgrade ripgrep",
        "upgrade_note": "Homebrew",
        "latest": {"type": "homebrew", "formula": "ripgrep"},
    },
    "eza": {
        "desc": "Modern replacement for ls",
        "local_cmd": "eza --version",
        "local_regex": r"v(\d+\.\d+\.\d+)",
        "upgrade_cmd": "brew upgrade eza",
        "upgrade_note": "Homebrew",
        "latest": {"type": "homebrew", "formula": "eza"},
    },
    "ruff": {
        "desc": "An extremely fast Python linter and code formatter",
        "local_cmd": "ruff --version",
        "local_regex": r"ruff\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "uv tool upgrade ruff",
        "upgrade_note": "uv tool",
        "latest": {"type": "pypi", "package": "ruff"},
    },
    "mypy": {
        "desc": "Optional static typing for Python",
        "local_cmd": "mypy --version",
        "local_regex": r"mypy\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "uv tool upgrade mypy",
        "upgrade_note": "uv tool",
        "latest": {"type": "pypi", "package": "mypy"},
    },
    "pyright": {
        "desc": "Static type checker for Python",
        "local_cmd": "pyright --version",
        "local_regex": r"(\d+\.\d+\.\d+)",
        "upgrade_cmd": "npm install -g pyright",
        "upgrade_note": "npm",
        "latest": {"type": "npm", "package": "pyright"},
    },
    "node": {
        "desc": "Node.js JavaScript runtime",
        "local_cmd": "node --version",
        "local_regex": r"v(\d+\.\d+\.\d+)",
        "upgrade_cmd": "brew upgrade node",
        "upgrade_note": "Homebrew",
        "latest": {"type": "homebrew", "formula": "node"},
    },
    "pnpm": {
        "desc": "Fast, disk space efficient package manager",
        "local_cmd": "pnpm --version",
        "local_regex": r"(\d+\.\d+\.\d+)",
        "upgrade_cmd": "npm install -g pnpm",
        "upgrade_note": "npm",
        "latest": {"type": "npm", "package": "pnpm"},
    },
    "tsc": {
        "desc": "TypeScript compiler",
        "local_cmd": "tsc --version",
        "local_regex": r"Version\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "npm install -g typescript",
        "upgrade_note": "npm",
        "latest": {"type": "npm", "package": "typescript"},
    },
    "go": {
        "desc": "Go programming language",
        "local_cmd": "go version",
        "local_regex": r"go\d+\.(\d+\.\d+)",
        "upgrade_cmd": "brew upgrade go",
        "upgrade_note": "Homebrew",
        "latest": {"type": "homebrew", "formula": "go"},
    },
    "cargo": {
        "desc": "Rust package manager",
        "local_cmd": "cargo --version",
        "local_regex": r"cargo\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "rustup update",
        "upgrade_note": "rustup",
        "latest": {"type": "github_release", "repo": "rust-lang/cargo", "tag_prefix": ""},
    },
    "rustfmt": {
        "desc": "Rust code formatter",
        "local_cmd": "rustfmt --version",
        "local_regex": r"rustfmt\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "rustup update",
        "upgrade_note": "rustup",
        "latest": {"type": "github_tag", "repo": "rust-lang/rustfmt", "tag_prefix": ""},
    },
    "golangci-lint": {
        "desc": "Fast linters runner for Go",
        "local_cmd": "golangci-lint --version",
        "local_regex": r"golangci-lint\s+has\s+version\s+(\d+\.\d+\.\d+)",
        "upgrade_cmd": "brew upgrade golangci-lint",
        "upgrade_note": "Homebrew",
        "latest": {"type": "homebrew", "formula": "golangci-lint"},
    },
    "rtk": {
        "desc": "Rust Token Killer，CLI 输出压缩代理",
        "local_cmd": "rtk --version",
        "local_regex": r"(?:rtk\s+)?(\d+\.\d+\.\d+)",
        "upgrade_cmd": "curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh",
        "upgrade_note": "rtk official install.sh",
        "latest": {"type": "github_release", "repo": "rtk-ai/rtk", "tag_prefix": "v"},
    },
    "codegraph": {
        "desc": "代码符号知识图谱 MCP server",
        "local_cmd": "codegraph version",
        "local_regex": r"(\d+\.\d+\.\d+)",
        "upgrade_cmd": "codegraph upgrade",
        "upgrade_note": "codegraph built-in upgrader",
        "latest": {"type": "builtin_check", "cmd": "codegraph upgrade --check", "regex": r"latest\s+v?(\d+\.\d+\.\d+)"},
    },
    "agent-reach": {
        "desc": "Multi-platform web retrieval backend",
        "local_cmd": "agent-reach --version",
        "local_regex": r"v?(\d+\.\d+\.\d+)",
        "upgrade_cmd": "uv tool upgrade --force agent-reach",
        "upgrade_note": "uv tool from GitHub main",
        "latest": {"type": "github_raw", "repo": "Panniantong/agent-reach", "branch": "main", "file": "agent_reach/__init__.py", "regex": r'__version__\s*=\s*"(\d+\.\d+\.\d+)"'},
    },
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Component:
    name: str
    desc: str
    binary: str
    local_cmd: str
    local_regex: str
    upgrade_cmd: str
    upgrade_note: str
    latest_type: str
    latest_cfg: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    return ansi.sub("", text)


def parse_version(text: str, pattern: str) -> str | None:
    """Apply regex to text and return the first captured group."""
    m = re.search(pattern, text)
    if m:
        return m.group(1)
    return None


def version_tuple(v: str) -> tuple[int, ...]:
    """Convert 'x.y.z' to (x, y, z), padding missing parts with 0."""
    parts = [int(x) for x in v.split(".") if x.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def cmp_version(local: str, latest: str) -> str:
    """Return 'latest' if local == latest, 'outdated' if local < latest, else 'ahead'."""
    lt = version_tuple(local)
    rt = version_tuple(latest)
    if lt == rt:
        return "latest"
    if lt < rt:
        return "outdated"
    return "ahead"


def _curl_get(url: str, timeout: int = 30) -> str:
    """Fallback HTTP fetch using curl (macOS uv Python sometimes fails SSL handshake on raw.githubusercontent)."""
    cmd = f"curl -fsSL -H 'User-Agent: {USER_AGENT}' --max-time {timeout} {url!r}"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout + 5)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def http_get_json(url: str) -> dict:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return json.loads(_curl_get(url))


def http_get_text(url: str) -> str:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return _curl_get(url)


def run_shell(cmd: str, timeout: int = 20) -> tuple[int, str, str]:
    """Run a shell command and return (exit_code, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# Version resolution
# ---------------------------------------------------------------------------


def get_local_version(comp: Component) -> dict:
    """Detect local installed version of a component."""
    binary_path = shutil.which(comp.binary)
    if not binary_path:
        return {
            "name": comp.name,
            "local": "-",
            "latest": "-",
            "status": "not_installed",
            "source": f"binary not found: {comp.binary}",
            "upgrade_cmd": comp.upgrade_cmd,
            "upgrade_note": comp.upgrade_note,
        }

    code, stdout, stderr = run_shell(comp.local_cmd)
    output = stdout or stderr or ""
    version = parse_version(output, comp.local_regex)
    if not version:
        return {
            "name": comp.name,
            "local": "-",
            "latest": "-",
            "status": "error",
            "source": f"local regex did not match output: {output!r}",
            "upgrade_cmd": comp.upgrade_cmd,
            "upgrade_note": comp.upgrade_note,
        }

    return {
        "name": comp.name,
        "local": version,
        "latest": None,
        "status": "pending",
        "source": "",
        "upgrade_cmd": comp.upgrade_cmd,
        "upgrade_note": comp.upgrade_note,
    }


def fetch_latest(comp: Component) -> dict:
    """Fetch the latest version from the configured source."""
    ctype = comp.latest_type
    cfg = comp.latest_cfg
    try:
        if ctype == "github_release":
            repo = cfg["repo"]
            prefix = cfg.get("tag_prefix", "")
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            data = http_get_json(url)
            tag = data.get("tag_name", "")
            if prefix and tag.startswith(prefix):
                version = tag[len(prefix):]
            else:
                version = tag
            return {
                "latest": version or None,
                "source": f"github_release:{repo}",
                "error": None,
            }

        if ctype == "github_raw":
            repo = cfg["repo"]
            branch = cfg.get("branch", "main")
            file_path = cfg["file"]
            pattern = cfg["regex"]
            url = f"https://raw.githubusercontent.com/{repo}/{branch}/{file_path}"
            text = http_get_text(url)
            version = parse_version(text, pattern)
            return {
                "latest": version,
                "source": f"github_raw:{repo}",
                "error": None,
            }

        if ctype == "github_tag":
            repo = cfg["repo"]
            prefix = cfg.get("tag_prefix", "")
            url = f"https://api.github.com/repos/{repo}/tags?per_page=1"
            data = http_get_json(url)
            tag = data[0].get("name", "") if data else ""
            if prefix and tag.startswith(prefix):
                version = tag[len(prefix):]
            else:
                version = tag
            return {
                "latest": version or None,
                "source": f"github_tag:{repo}",
                "error": None,
            }

        if ctype == "builtin_check":
            cmd = cfg["cmd"]
            pattern = cfg["regex"]
            code, stdout, stderr = run_shell(cmd, timeout=30)
            output = stdout or stderr or ""
            output = strip_ansi(output)
            version = parse_version(output, pattern)
            return {
                "latest": version,
                "source": "builtin_check",
                "error": None,
            }

        if ctype == "pypi":
            package = cfg["package"]
            url = f"https://pypi.org/pypi/{package}/json"
            data = http_get_json(url)
            version = data.get("info", {}).get("version")
            return {
                "latest": version,
                "source": f"pypi:{package}",
                "error": None,
            }

        if ctype == "crates":
            crate = cfg["crate"]
            url = f"https://crates.io/api/v1/crates/{crate}"
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            version = data.get("crate", {}).get("max_version")
            return {
                "latest": version,
                "source": f"crates:{crate}",
                "error": None,
            }

        if ctype == "npm":
            package = cfg["package"]
            url = f"https://registry.npmjs.org/{package}"
            data = http_get_json(url)
            version = data.get("dist-tags", {}).get("latest")
            return {
                "latest": version,
                "source": f"npm:{package}",
                "error": None,
            }

        if ctype == "homebrew":
            formula = cfg["formula"]
            code, stdout, stderr = run_shell(f"brew info --json {formula}", timeout=30)
            if code == 0 and stdout.strip():
                try:
                    data = json.loads(stdout)
                    if isinstance(data, list) and data:
                        version = data[0].get("versions", {}).get("stable")
                        if version:
                            return {
                                "latest": version,
                                "source": f"homebrew:{formula}",
                                "error": None,
                            }
                except json.JSONDecodeError:
                    pass
            output = (stdout or stderr or "").strip()
            version = parse_version(output, r"[\s/:](\d+\.\d+(?:\.\d+)?)")
            return {
                "latest": version,
                "source": f"homebrew:{formula}",
                "error": None,
            }

        return {
            "latest": None,
            "source": ctype,
            "error": f"unsupported latest type: {ctype}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "latest": None,
            "source": ctype,
            "error": f"{type(exc).__name__}: {exc}",
        }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def load_components() -> list[Component]:
    if not CONFIG_PATH.exists():
        print(f"Config not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)

    comps = []
    for raw in data.get("component", []):
        latest = raw.get("latest", {})
        comps.append(
            Component(
                name=raw["name"],
                desc=raw.get("desc", ""),
                binary=raw.get("binary", raw["name"]),
                local_cmd=raw["local_cmd"],
                local_regex=raw["local_regex"],
                upgrade_cmd=raw["upgrade_cmd"],
                upgrade_note=raw.get("upgrade_note", ""),
                latest_type=latest.get("type", ""),
                latest_cfg=latest,
            )
        )
    return comps


def cmd_check() -> int:
    comps = load_components()
    results: list[dict] = []

    # Phase 1: local versions (parallel)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        local_results = list(executor.map(get_local_version, comps))

    # Phase 2: fetch latest only for installed components (parallel)
    installed = [(i, r) for i, r in enumerate(local_results) if r["status"] == "pending"]
    latest_futures: dict[int, concurrent.futures.Future] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for idx, res in installed:
            comp = comps[idx]
            future = executor.submit(fetch_latest, comp)
            latest_futures[idx] = future

    # Combine
    for idx, res in enumerate(local_results):
        comp = comps[idx]
        if res["status"] in ("not_installed", "error"):
            results.append(res)
            continue

        latest_info = latest_futures[idx].result()
        latest = latest_info.get("latest")
        error = latest_info.get("error")

        if error or not latest:
            res["latest"] = latest or "-"
            res["status"] = "error"
            res["source"] = error or "failed to fetch latest version"
        else:
            res["latest"] = latest
            res["status"] = cmp_version(res["local"], latest)
            res["source"] = latest_info.get("source", "")

        results.append(res)

    # Print table
    headers = ["COMPONENT", "LOCAL", "LATEST", "STATUS", "SOURCE"]
    rows = [headers]
    for r in results:
        rows.append(
            [r["name"], r["local"], r["latest"], r["status"], r["source"]]
        )

    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    for row in rows:
        line = "  ".join(
            cell.ljust(widths[i]) for i, cell in enumerate(row)
        )
        print(line)

    print()

    outdated = [r for r in results if r["status"] == "outdated"]
    if outdated:
        print("Upgrade candidates:")
        for r in outdated:
            print(f"  {r['name']}:")
            print(f"    cmd:   {r['upgrade_cmd']}")
            if r["upgrade_note"]:
                print(f"    note:  {r['upgrade_note']}")
        print("\nConfirm which component(s) to upgrade.")
    else:
        print("No outdated components.")

    return 0


def cmd_list() -> int:
    comps = load_components()
    headers = ["NAME", "DESC", "BINARY", "LATEST_TYPE"]
    rows = [headers]
    for c in comps:
        binary_path = shutil.which(c.binary) or "(not found)"
        rows.append([c.name, c.desc, binary_path, c.latest_type])

    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    for row in rows:
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        print(line)
    return 0


def cmd_upgrade(name: str) -> int:
    comps = load_components()
    comp = next((c for c in comps if c.name == name), None)
    if not comp:
        print(f"Unknown component: {name}", file=sys.stderr)
        return 1

    print(f"Component: {comp.name}")
    print("Upgrade command (requires confirmation before execution):")
    print(f"  {comp.upgrade_cmd}")
    if comp.upgrade_note:
        print(f"Note: {comp.upgrade_note}")
    print("\nThis command modifies globally-installed binaries. Confirm before running.")
    return 0


def _preset_dir() -> Path:
    return CONFIG_PATH.parent / "presets"


def cmd_preset_list() -> int:
    preset_dir = _preset_dir()
    if not preset_dir.exists():
        print(f"No presets directory: {preset_dir}")
        return 0

    files = sorted(preset_dir.glob("*.toml"))
    if not files:
        print("No presets found.")
        return 0

    print("Available presets:")
    for f in files:
        print(f"  {f.stem}")
    return 0


def cmd_preset_import(name_or_path: str) -> int:
    path = Path(name_or_path)
    if not path.exists():
        # Try resolving against presets dir
        candidate = _preset_dir() / f"{name_or_path}.toml"
        if candidate.exists():
            path = candidate
        else:
            print(f"Preset not found: {name_or_path}", file=sys.stderr)
            return 1

    with path.open("rb") as f:
        data = tomllib.load(f)

    new_components = data.get("component", [])
    if not new_components:
        print(f"Preset contains no components: {path}")
        return 0

    # Load existing names to warn about duplicates
    existing = {c.name for c in load_components()}
    added = []
    skipped = []
    for raw in new_components:
        comp_name = raw.get("name")
        if comp_name in existing:
            skipped.append(comp_name)
        else:
            added.append(comp_name)

    if not added:
        print(f"All components from {path.name} already exist in {CONFIG_PATH}")
        return 0

    # Append raw TOML text
    with CONFIG_PATH.open("a", encoding="utf-8") as out:
        out.write("\n")
        out.write(f"# Imported from preset: {path.name}\n")
        out.write(path.read_text(encoding="utf-8"))
        out.write("\n")

    print(f"Imported {len(added)} component(s) from {path.name}:")
    for name in added:
        print(f"  + {name}")
    if skipped:
        print(f"Skipped {len(skipped)} duplicate(s):")
        for name in skipped:
            print(f"  - {name}")
    return 0


def _path_binaries() -> set[str]:
    """Return all executable names found in PATH."""
    found: set[str] = set()
    for dir_path in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(dir_path)
        if not p.is_dir():
            continue
        try:
            for entry in p.iterdir():
                if entry.is_file() and os.access(entry, os.X_OK):
                    found.add(entry.name)
        except OSError:
            continue
    return found


def _render_toml_component(name: str, cfg: dict) -> str:
    lines = [f'[[component]]', f'name = "{name}"', f'desc = "{cfg["desc"]}"']
    binary = cfg.get("binary", name)
    if binary != name:
        lines.append(f'binary = "{binary}"')
    lines.append(f'local_cmd = "{cfg["local_cmd"]}"')
    lines.append(f'local_regex = \'{cfg["local_regex"]}\'')
    if cfg.get("upgrade_cmd"):
        lines.append(f'upgrade_cmd = \'{cfg["upgrade_cmd"]}\'')
    if cfg.get("upgrade_note"):
        lines.append(f'upgrade_note = "{cfg["upgrade_note"]}"')
    latest = cfg.get("latest", {})
    lines.append("")
    lines.append("[component.latest]")
    for key, value in latest.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f'{key} = "{value}"')
    return "\n".join(lines)


def cmd_discover() -> int:
    """Scan PATH for known tools and emit candidate components.toml entries."""
    existing = {c.name for c in load_components()}
    binaries = _path_binaries()
    candidates: list[tuple[str, dict]] = []
    for name, cfg in KNOWN_TOOLS.items():
        binary = cfg.get("binary", name)
        if binary in binaries and name not in existing:
            candidates.append((name, cfg))

    if not candidates:
        print("No new known tools discovered in PATH.")
        return 0

    print(f"Discovered {len(candidates)} tool(s) not yet in {CONFIG_PATH}:\n")
    for name, cfg in candidates:
        print(_render_toml_component(name, cfg))
        print()

    print("To add them, copy the blocks above into your components.toml")
    print("or run: oss-version preset import <preset-name>")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="oss-version",
        description="Check and manage versions of locally-installed open-source CLI tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Check local vs latest versions")
    sub.add_parser("list", help="List registered components")

    p_upgrade = sub.add_parser("upgrade", help="Print upgrade command for a component")
    p_upgrade.add_argument("name", help="Component name")

    p_preset = sub.add_parser("preset", help="Manage presets")
    p_preset_sub = p_preset.add_subparsers(dest="preset_command", required=True)
    p_preset_sub.add_parser("list", help="List available presets")
    p_preset_import = p_preset_sub.add_parser("import", help="Import a preset into components.toml")
    p_preset_import.add_argument("name_or_path", help="Preset name or path to a .toml file")

    sub.add_parser("discover", help="Scan PATH for known tools")

    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check()
    if args.command == "list":
        return cmd_list()
    if args.command == "upgrade":
        return cmd_upgrade(args.name)
    if args.command == "preset":
        if args.preset_command == "list":
            return cmd_preset_list()
        if args.preset_command == "import":
            return cmd_preset_import(args.name_or_path)
    if args.command == "discover":
        return cmd_discover()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
