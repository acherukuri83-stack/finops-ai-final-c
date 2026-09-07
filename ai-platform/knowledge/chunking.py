"""Section-aware chunking of the corpus markdown.

- SOP docs: front-matter `doc:` (the citation name), then `## §<num> — <title>` sections.
  One chunk per section; `section` is the `§…` token, `title` the rest.
- Incident docs (`kind: incident`): the whole doc is one chunk; front-matter carries
  `incident_id`, `summary`, `root_cause`, `resolution`.
- Fixture docs (`kind: fixture`): one chunk, `doc:` is the citation name, no section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_SECTION = re.compile(r"^##\s+(§\S+)\s*[—-]\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class Chunk:
    id: str
    kind: str  # sop | incident | fixture
    text: str  # what gets embedded
    doc: str = ""
    section: str = ""
    title: str = ""
    incident_id: str = ""
    summary: str = ""
    root_cause: str = ""
    resolution: str = ""
    extra: dict[str, str] = field(default_factory=dict)


def _front_matter(raw: str) -> tuple[dict[str, str], str]:
    m = _FRONT_MATTER.match(raw)
    if not m:
        return {}, raw
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, raw[m.end() :]


def chunk_file(path: Path) -> list[Chunk]:
    meta, body = _front_matter(path.read_text(encoding="utf-8"))
    kind = meta.get("kind", "sop")

    if kind == "incident":
        inc = meta["incident_id"]
        text = " ".join(
            filter(
                None,
                [meta.get("summary"), meta.get("root_cause"), meta.get("resolution"), body.strip()],
            )
        )
        return [
            Chunk(
                id=inc,
                kind="incident",
                text=text,
                incident_id=inc,
                summary=meta.get("summary", ""),
                root_cause=meta.get("root_cause", ""),
                resolution=meta.get("resolution", ""),
            )
        ]

    if kind == "fixture":
        doc = meta.get("doc", path.stem)
        return [
            Chunk(id=doc, kind="fixture", text=body.strip(), doc=doc, title=meta.get("title", doc))
        ]

    doc = meta["doc"]
    chunks: list[Chunk] = []
    marks = list(_SECTION.finditer(body))
    for i, mark in enumerate(marks):
        section = mark.group(1).lstrip("§")  # store "8.4"; cite as "<doc> §<section>"
        title = mark.group(2).strip()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        section_text = body[mark.end() : end].strip()
        chunks.append(
            Chunk(
                id=f"{doc} §{section}",
                kind="sop",
                text=f"{doc} §{section} — {title}\n{section_text}",
                doc=doc,
                section=section,
                title=title,
            )
        )
    return chunks
