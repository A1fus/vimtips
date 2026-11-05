from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Final, Mapping, Pattern, TypedDict, cast


class VimTipError(Exception):
    pass


@dataclass(frozen=True)
class Tip:
    tag: str
    mode: str
    key: str
    description: str
    editors: tuple[str, ...]


class _ParsedEntry(TypedDict):
    mode: str
    key: str
    description: list[str]
    editors: set[str]


class RotationState(TypedDict, total=False):
    version: int
    seen: list[str]
    last_date: str
    last_tip: str


MODE_TAGS: Final[dict[str, str]] = {
    "insert-index": "Insert",
    "normal-index": "Normal",
    "visual-index": "Visual",
    "ex-cmd-index": "Ex",
}
MODE_HEADING: Final[Pattern[str]] = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
HELP_TAG: Final[Pattern[str]] = re.compile(r"\*([^*]+)\*")
TAG_ROW: Final[Pattern[str]] = re.compile(r"^\s*\|([^|]+)\|\s*(.*)$")
IGNORED_DESCRIPTIONS: Final[tuple[str, ...]] = (
    "not used",
    "reserved",
    "not implemented",
)


def parse_index(text: str, editor: str) -> list[Tip]:
    entries: dict[str, _ParsedEntry] = {}
    mode: str | None = None
    current: _ParsedEntry | None = None

    for line in text.splitlines():
        if MODE_HEADING.match(line):
            section_tags = HELP_TAG.findall(line)
            index_tag = next((tag for tag in section_tags if tag.endswith("-index")), None)
            if index_tag is not None:
                mode = MODE_TAGS.get(index_tag)
                current = None

        match = TAG_ROW.match(line) if mode is not None else None
        if match:
            assert mode is not None
            tag = match.group(1).strip()
            fields = [field.strip() for field in match.group(2).split("\t") if field.strip()]
            if len(fields) < 2:
                current = None
                continue

            key = fields[0]
            description = " ".join(fields[1:])
            if description.casefold().startswith(IGNORED_DESCRIPTIONS):
                current = None
                continue

            current = entries.setdefault(
                tag,
                _ParsedEntry(
                    mode=mode,
                    key=key,
                    description=[],
                    editors=set(),
                ),
            )
            current["editors"].add(editor)
            existing_description = " ".join(current["description"]).strip()
            if description != existing_description and description not in current["description"]:
                current["description"].append(description)
            continue

        if current is None or not line.strip() or "*" in line:
            continue

        fields = [field.strip() for field in line.split("\t") if field.strip()]
        if len(fields) == 1:
            if fields[0] not in current["description"]:
                current["description"].append(fields[0])
        else:
            current = None

    return [
        Tip(
            tag=tag,
            mode=str(entry["mode"]),
            key=str(entry["key"]),
            description=re.sub(r"\s+", " ", " ".join(entry["description"])).strip(),
            editors=tuple(sorted(entry["editors"])),
        )
        for tag, entry in entries.items()
    ]


def merge_indexes(indexes: Mapping[str, str]) -> list[Tip]:
    merged: dict[str, Tip] = {}
    for editor, text in indexes.items():
        for tip in parse_index(text, editor):
            previous = merged.get(tip.tag)
            if previous is None:
                merged[tip.tag] = tip
            else:
                merged[tip.tag] = Tip(
                    tag=tip.tag,
                    mode=previous.mode,
                    key=previous.key,
                    description=previous.description,
                    editors=tuple(sorted(set(previous.editors) | set(tip.editors))),
                )
    return list(merged.values())


def vim_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def discover_runtime(editor: str, binary: str) -> Path:
    with tempfile.TemporaryDirectory(prefix="vimtip-") as temporary_directory:
        output_path = Path(temporary_directory) / "runtime.txt"
        command = (
            f"call writefile([expand('$VIMRUNTIME')], {vim_string(str(output_path))})"
        )
        if editor == "Vim":
            arguments = [
                binary,
                "-N",
                "-u",
                "NONE",
                "-U",
                "NONE",
                "-n",
                "-i",
                "NONE",
                "--noplugin",
                "-es",
            ]
        else:
            arguments = [
                binary,
                "--clean",
                "--headless",
                "-n",
                "-u",
                "NONE",
                "-i",
                "NONE",
            ]

        try:
            result = subprocess.run(
                [*arguments, "-c", command, "-c", "qa!"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VimTipError(f"could not query {editor} runtime: {error}") from error

        if result.returncode != 0 or not output_path.is_file():
            detail = result.stderr.strip() or "runtime path was not returned"
            raise VimTipError(f"could not query {editor} runtime: {detail}")

        runtime = output_path.read_text(encoding="utf-8").strip()
        if not runtime:
            raise VimTipError(f"{editor} did not report a runtime path")
        return Path(runtime)


def load_indexes() -> dict[str, str]:
    indexes: dict[str, str] = {}
    for editor, executable in (("Vim", "vim"), ("Neovim", "nvim")):
        binary = shutil.which(executable)
        if binary is None:
            raise VimTipError(f"required editor not found: {executable}")

        runtime = discover_runtime(editor, binary)
        index_path = runtime / "doc" / "index.txt"
        if not index_path.is_file():
            raise VimTipError(
                f"{editor} help index not found at {index_path}; install its documentation"
            )
        indexes[editor] = index_path.read_text(encoding="utf-8", errors="replace")
    return indexes


def default_state_directory() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "vimtip"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "vimtip"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "vimtip"


def read_state(path: Path) -> RotationState:
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(decoded, dict):
        return {}

    raw_state = cast(dict[str, object], decoded)
    seen_value = raw_state.get("seen")
    last_date = raw_state.get("last_date")
    last_tip = raw_state.get("last_tip")
    if not isinstance(seen_value, list):
        return {}
    if not isinstance(last_date, str) or not isinstance(last_tip, str):
        return {}

    seen_items = cast(list[object], seen_value)
    seen = [tag for tag in seen_items if isinstance(tag, str)]
    if len(seen) != len(seen_items):
        return {}

    version = raw_state.get("version")
    return RotationState(
        version=version if isinstance(version, int) else 1,
        seen=seen,
        last_date=last_date,
        last_tip=last_tip,
    )


def write_state(path: Path, state: RotationState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(prefix=".vimtip-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as state_file:
            json.dump(state, state_file, sort_keys=True)
            state_file.write("\n")
            state_file.flush()
            os.fsync(state_file.fileno())
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def choose_tip(
    tips: list[Tip],
    state: RotationState,
    today: date,
    chooser: Callable[[list[Tip]], Tip] = random.choice,
) -> tuple[Tip, RotationState]:
    if not tips:
        raise VimTipError("no actionable commands found in the installed help indexes")

    by_tag = {tip.tag: tip for tip in tips}
    today_text = today.isoformat()
    last_tip = state.get("last_tip")
    if (
        state.get("last_date") == today_text
        and isinstance(last_tip, str)
        and last_tip in by_tag
    ):
        return by_tag[last_tip], state

    stored_seen = state.get("seen", [])
    seen: set[str] = {tag for tag in stored_seen if tag in by_tag}
    available = [tip for tip in tips if tip.tag not in seen]
    if not available:
        seen.clear()
        available = tips

    selected = chooser(available)
    updated_state = RotationState(
        version=1,
        seen=sorted(seen | {selected.tag}),
        last_date=today_text,
        last_tip=selected.tag,
    )
    return selected, updated_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show one Vim tip per day.")
    parser.add_argument(
        "--reset", action="store_true", help="start a fresh tip rotation"
    )
    arguments = parser.parse_args(argv)

    try:
        tips = merge_indexes(load_indexes())
        state_path = default_state_directory() / "state.json"
        state = RotationState() if arguments.reset else read_state(state_path)
        tip, updated_state = choose_tip(tips, state, date.today())
        write_state(state_path, updated_state)
    except (OSError, VimTipError) as error:
        print(f"vimtip: {error}", file=sys.stderr)
        return 1

    print(f"{tip.mode}: {tip.key} - {tip.description}")
    print(f"Documented by: {', '.join(tip.editors)}")
    print(f"Help: :help {tip.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())