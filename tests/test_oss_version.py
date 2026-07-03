"""Tests for oss-version core logic."""

from pathlib import Path

import pytest

from oss_version import (
    Component,
    cmp_version,
    get_local_version,
    load_components,
    parse_version,
    render_upgrade_cmd,
    version_tuple,
)


# ---------------------------------------------------------------------------
# Version parsing / comparison
# ---------------------------------------------------------------------------


def test_parse_version_simple():
    assert parse_version("uv 0.11.26", r"uv\s+(\d+\.\d+\.\d+)") == "0.11.26"


def test_parse_version_missing():
    assert parse_version("no version here", r"(\d+\.\d+\.\d+)") is None


def test_version_tuple_pads():
    assert version_tuple("1.2") == (1, 2, 0)
    assert version_tuple("1.2.3") == (1, 2, 3)


def test_cmp_version():
    assert cmp_version("1.2.3", "1.2.3") == "latest"
    assert cmp_version("1.2.3", "1.2.4") == "outdated"
    assert cmp_version("1.2.4", "1.2.3") == "ahead"


# ---------------------------------------------------------------------------
# Upgrade command rendering
# ---------------------------------------------------------------------------


def test_render_upgrade_cmd_substitutes_version_tag_repo():
    comp = Component(
        name="demo",
        desc="",
        binary=None,
        local_cmd="",
        local_regex="",
        upgrade_cmd='echo "{version}" "{tag}" "{repo}"',
        upgrade_note="",
        latest_type="github_release",
        latest_cfg={"repo": "owner/repo", "tag_prefix": "v"},
    )
    rendered = render_upgrade_cmd(comp.upgrade_cmd, comp, "3.16.5", "v3.16.5")
    assert rendered == 'echo "3.16.5" "v3.16.5" "owner/repo"'


def test_render_upgrade_cmd_no_templates():
    comp = Component(
        name="demo",
        desc="",
        binary=None,
        local_cmd="",
        local_regex="",
        upgrade_cmd="brew upgrade demo",
        upgrade_note="",
        latest_type="homebrew",
        latest_cfg={"formula": "demo"},
    )
    assert render_upgrade_cmd(comp.upgrade_cmd, comp, "1.0.0") == "brew upgrade demo"


def test_render_upgrade_cmd_tag_fallback_to_version():
    comp = Component(
        name="demo",
        desc="",
        binary=None,
        local_cmd="",
        local_regex="",
        upgrade_cmd="echo {tag}",
        upgrade_note="",
        latest_type="pypi",
        latest_cfg={"package": "demo"},
    )
    assert render_upgrade_cmd(comp.upgrade_cmd, comp, "1.0.0") == "echo 1.0.0"


# ---------------------------------------------------------------------------
# Local version detection
# ---------------------------------------------------------------------------


def test_get_local_version_success(monkeypatch):
    comp = Component(
        name="demo",
        desc="",
        binary="demo",
        local_cmd="demo --version",
        local_regex=r"(\d+\.\d+\.\d+)",
        upgrade_cmd="",
        upgrade_note="",
        latest_type="",
        latest_cfg={},
    )

    def fake_run(cmd, timeout=20):
        assert cmd == "demo --version"
        return 0, "demo version 1.2.3\n", ""

    monkeypatch.setattr("oss_version.run_shell", fake_run)
    result = get_local_version(comp)
    assert result["status"] == "pending"
    assert result["local"] == "1.2.3"


def test_get_local_version_not_installed(monkeypatch):
    comp = Component(
        name="demo",
        desc="",
        binary=None,
        local_cmd="demo --version",
        local_regex=r"(\d+\.\d+\.\d+)",
        upgrade_cmd="",
        upgrade_note="",
        latest_type="",
        latest_cfg={},
    )

    def fake_run(cmd, timeout=20):
        return 127, "", "command not found: demo"

    monkeypatch.setattr("oss_version.run_shell", fake_run)
    result = get_local_version(comp)
    assert result["status"] == "not_installed"


def test_get_local_version_regex_error(monkeypatch):
    comp = Component(
        name="demo",
        desc="",
        binary=None,
        local_cmd="demo --version",
        local_regex=r"(\d+\.\d+\.\d+)",
        upgrade_cmd="",
        upgrade_note="",
        latest_type="",
        latest_cfg={},
    )

    def fake_run(cmd, timeout=20):
        return 0, "unexpected output\n", ""

    monkeypatch.setattr("oss_version.run_shell", fake_run)
    result = get_local_version(comp)
    assert result["status"] == "error"
    assert "local regex did not match" in result["source"]


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def test_load_components_parses_optional_binary(tmp_path, monkeypatch):
    config = tmp_path / "components.toml"
    config.write_text(
        r'''
[[component]]
name = "gui-app"
desc = "A GUI app"
local_cmd = "echo 1.0.0"
local_regex = '(\d+\.\d+\.\d+)'
upgrade_cmd = "echo {version}"

[component.latest]
type = "github_release"
repo = "owner/repo"
tag_prefix = "v"

[[component]]
name = "cli-tool"
binary = "cli-tool"
local_cmd = "cli-tool --version"
local_regex = '(\d+\.\d+\.\d+)'
upgrade_cmd = "brew upgrade cli-tool"

[component.latest]
type = "homebrew"
formula = "cli-tool"
'''
    )
    monkeypatch.setattr("oss_version.CONFIG_PATH", config)
    comps = load_components()
    assert len(comps) == 2
    assert comps[0].name == "gui-app"
    assert comps[0].binary is None
    assert comps[1].name == "cli-tool"
    assert comps[1].binary == "cli-tool"
