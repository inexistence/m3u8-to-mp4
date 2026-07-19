#!/usr/bin/env python3
"""Build GitHub Release notes from CHANGELOG.md or git commits."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HEADING_RE = re.compile(
    r"^##\s+(?:\[)?(?P<label>v?\d+\.\d+\.\d[^\]\s]*)(?:\])?(?:[^\n]*)?$",
    re.MULTILINE | re.IGNORECASE,
)
_PRERELEASE_RE = re.compile(r"-(?:alpha|beta|rc)", re.IGNORECASE)

DEFAULT_FOOTER = (
    "---\n"
    "- Windows standalone executable; Python not required\n"
    "- FFmpeg is bundled via imageio-ffmpeg\n"
    "- Third-party licenses: see THIRD_PARTY_NOTICES.md\n"
)


def normalize_version(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("version is empty")
    return raw if raw.lower().startswith("v") else f"v{raw}"


def is_prerelease(tag: str) -> bool:
    return bool(_PRERELEASE_RE.search(tag))


def _version_core(version: str) -> str:
    v = normalize_version(version)
    return v[1:] if v.lower().startswith("v") else v


def extract_changelog_section(text: str, version: str) -> str | None:
    target = _version_core(version).lower()
    matches = list(_HEADING_RE.finditer(text))
    for i, match in enumerate(matches):
        label = match.group("label")
        core = label[1:] if label.lower().startswith("v") else label
        if core.lower() != target:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        return body or None
    return None


def build_notes(
    *,
    changelog_path: Path | None,
    version: str,
    override: str | None,
    commits_text: str | None,
    footer: str,
) -> str:
    if override is not None and override.strip():
        main = override.strip()
    else:
        main = None
        if changelog_path is not None and changelog_path.is_file():
            main = extract_changelog_section(_read_text(changelog_path), version)
        if not main:
            commits = (commits_text or "").strip()
            main = commits if commits else f"Release {normalize_version(version)}"
    footer = footer.strip()
    if footer:
        return f"{main.rstrip()}\n\n{footer}\n"
    return f"{main.rstrip()}\n"


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--override", default=None)
    parser.add_argument("--commits-file", type=Path, default=None)
    parser.add_argument("--footer-file", type=Path, default=None)
    parser.add_argument("--check-prerelease", action="store_true")
    args = parser.parse_args(argv)

    version = normalize_version(args.version)
    if args.check_prerelease:
        print("true" if is_prerelease(version) else "false")
        return 0

    commits_text = None
    if args.commits_file is not None and args.commits_file.is_file():
        commits_text = _read_text(args.commits_file)

    footer = DEFAULT_FOOTER
    if args.footer_file is not None and args.footer_file.is_file():
        footer = _read_text(args.footer_file)

    changelog = args.changelog if args.changelog.is_file() else None
    sys.stdout.write(
        build_notes(
            changelog_path=changelog,
            version=version,
            override=args.override,
            commits_text=commits_text,
            footer=footer,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
