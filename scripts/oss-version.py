#!/usr/bin/env python3
"""oss-version: check and manage versions of locally-installed open-source CLI tools."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
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

CONFIG_PATH = Path.home() / ".claude" / "skills" / "oss-version" / "components.toml"
USER_AGENT = "oss-version-check"


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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="oss-version.py",
        description="Check and manage versions of locally-installed open-source CLI tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Check local vs latest versions")
    sub.add_parser("list", help="List registered components")

    p_upgrade = sub.add_parser("upgrade", help="Print upgrade command for a component")
    p_upgrade.add_argument("name", help="Component name")

    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check()
    if args.command == "list":
        return cmd_list()
    if args.command == "upgrade":
        return cmd_upgrade(args.name)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
