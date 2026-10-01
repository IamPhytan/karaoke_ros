"""Minimal LRC parser, with support for word-level tags ("enhanced LRC").

Supported format:
    [ti:Title]  [ar:Artist]  [audio:file.ogg]   (metadata)
    [00:12.50]A line of lyrics
    [00:15.00]<00:15.00>Line <00:15.40>with <00:15.90>per-word <00:16.30>timing
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_TIME = r"(\d+):(\d+(?:\.\d+)?)"
LINE_TAG = re.compile(r"^\[" + _TIME + r"\]")
WORD_TAG = re.compile(r"<" + _TIME + r">")
META_TAG = re.compile(r"^\[([a-zA-Z_]+):(.*)\]$")


def _to_seconds(m: str, s: str) -> float:
    return int(m) * 60.0 + float(s)


@dataclass
class Word:
    time: float
    text: str


@dataclass
class Line:
    time: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Song:
    path: Path
    title: str
    artist: str
    lines: list[Line]
    audio: Optional[Path] = None
    tail: float = 3.0  # seconds added after the last line

    @property
    def duration(self) -> float:
        return (self.lines[-1].time + self.tail) if self.lines else 0.0

    def line_index_at(self, t: float) -> int:
        """Index of the active line at time t (-1 before the first line)."""
        idx = -1
        for i, line in enumerate(self.lines):
            if line.time <= t:
                idx = i
            else:
                break
        return idx

    def word_at(self, line_idx: int, t: float) -> str:
        """Active word of the given line at time t ("" if no word timing)."""
        if line_idx < 0 or line_idx >= len(self.lines):
            return ""
        word = ""
        for w in self.lines[line_idx].words:
            if w.time <= t:
                word = w.text
            else:
                break
        return word


def parse_lrc(path: Path) -> Song:
    title, artist, audio = path.stem, "", None
    lines: list[Line] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue

        # Metadata tags: [ti:...], [ar:...], [audio:...]
        meta = META_TAG.match(raw)
        if meta and not LINE_TAG.match(raw):
            key, val = meta.group(1).lower(), meta.group(2).strip()
            if key == "ti":
                title = val
            elif key == "ar":
                artist = val
            elif key == "audio":
                audio = (path.parent / val).resolve()
            continue

        # A line may carry several [mm:ss] tags (repeated choruses)
        times = []
        rest = raw
        while True:
            m = LINE_TAG.match(rest)
            if not m:
                break
            times.append(_to_seconds(m.group(1), m.group(2)))
            rest = rest[m.end() :]
        if not times:
            continue

        # Word-level split if <mm:ss> tags are present
        words: list[Word] = []
        parts = WORD_TAG.split(rest)
        # parts = [prefix, m1, s1, text1, m2, s2, text2, ...]
        if len(parts) > 1:
            for i in range(1, len(parts), 3):
                t = _to_seconds(parts[i], parts[i + 1])
                text = parts[i + 2].strip()
                if text:
                    words.append(Word(t, text))
        clean_text = WORD_TAG.sub("", rest).strip()

        # Duplicate the line for each timestamp, shifting word times accordingly
        for t in times:
            offset = t - (words[0].time if words else t)
            lines.append(
                Line(
                    time=t,
                    text=clean_text,
                    words=[Word(w.time + offset, w.text) for w in words],
                )
            )

    lines.sort(key=lambda l: l.time)

    # Fallback: look for an audio file with the same stem as the .lrc
    if audio is None:
        for ext in (".ogg", ".mp3", ".wav"):
            cand = path.with_suffix(ext)
            if cand.exists():
                audio = cand
                break
    return Song(path=path, title=title, artist=artist, lines=lines, audio=audio)
