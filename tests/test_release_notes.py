from pathlib import Path

from scripts.release_notes import (
    build_notes,
    extract_changelog_section,
    is_prerelease,
    normalize_version,
)


FOOTER = "---\nWindows standalone exe."


def test_normalize_version_adds_v():
    assert normalize_version("1.0.0") == "v1.0.0"
    assert normalize_version("v1.0.0") == "v1.0.0"


def test_is_prerelease():
    assert is_prerelease("v1.0.0-beta.1") is True
    assert is_prerelease("v1.0.0-rc1") is True
    assert is_prerelease("v1.0.0-ALPHA") is True
    assert is_prerelease("v1.0.0") is False


SAMPLE = """# Changelog

## [Unreleased]

- wip

## [1.0.0] - 2026-07-19

- First release

## [0.9.0]

- Older
"""


def test_extract_changelog_bracket_form():
    section = extract_changelog_section(SAMPLE, "v1.0.0")
    assert section is not None
    assert "First release" in section
    assert "Older" not in section
    assert "Unreleased" not in section


def test_extract_changelog_v_prefix_heading():
    text = "## v1.2.0\n\n- Feature\n\n## v1.1.0\n\n- Old\n"
    assert "Feature" in extract_changelog_section(text, "v1.2.0")


def test_extract_changelog_plain_heading():
    text = "## 2.0.0\n\n- Major\n"
    assert "Major" in extract_changelog_section(text, "v2.0.0")


def test_extract_missing_returns_none():
    assert extract_changelog_section(SAMPLE, "v9.9.9") is None


def test_build_notes_prefers_changelog(tmp_path: Path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE, encoding="utf-8")
    body = build_notes(
        changelog_path=path,
        version="v1.0.0",
        override=None,
        commits_text="- fake commit\n",
        footer=FOOTER,
    )
    assert "First release" in body
    assert "fake commit" not in body
    assert "Windows standalone" in body


def test_build_notes_falls_back_to_commits(tmp_path: Path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n\n## [Unreleased]\n\n- x\n", encoding="utf-8")
    body = build_notes(
        changelog_path=path,
        version="v1.0.0",
        override=None,
        commits_text="- abc Add thing\n",
        footer=FOOTER,
    )
    assert "Add thing" in body


def test_build_notes_override_wins(tmp_path: Path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE, encoding="utf-8")
    body = build_notes(
        changelog_path=path,
        version="v1.0.0",
        override="Manual notes only",
        commits_text="- commit\n",
        footer=FOOTER,
    )
    assert body.startswith("Manual notes only")
    assert "First release" not in body
