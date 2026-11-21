"""Loading of Annex A/B as UNTRUSTED input.

Every record is normalised, stripped of hidden Unicode, and scanned for
instruction-like content. Flagged records are quarantined: they stay in the
store (so the human reviewer can see what was removed and why) but no agent
tool will ever return their text.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .guards import HIDDEN_UNICODE_RE, scan_injection


@dataclass(frozen=True)
class SourceRecord:
    id: str
    annex: str  # "A", "B" or "extra" (red-team injected file)
    text: str  # sanitised text (for MOs: "name: pattern")
    basis: str
    quarantined: bool = False
    flags: tuple[str, ...] = ()
    name: str = ""


def sanitise(text: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    if HIDDEN_UNICODE_RE.search(text):
        flags.append("hidden_unicode")
        text = HIDDEN_UNICODE_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if ch.isprintable() or ch in " ")
    return text.strip(), flags


def _make(rec: dict, annex: str) -> SourceRecord:
    if annex == "A" or "pattern" in rec:
        raw = f"{rec['name']}: {rec['pattern']}"
    else:
        raw = rec["text"]
    clean, flags = sanitise(raw)
    flags += scan_injection(clean)
    return SourceRecord(
        id=rec["id"],
        annex=annex,
        text=clean,
        basis=rec.get("basis", "Unverified"),
        quarantined=bool(flags),
        flags=tuple(flags),
        name=rec.get("name", ""),
    )


@dataclass
class SourceStore:
    records: dict[str, SourceRecord] = field(default_factory=dict)
    file_hashes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, data_dir: Path, extra_records: list[dict] | None = None) -> "SourceStore":
        from .config import sha256_bytes

        store = cls()
        for fname, annex in (("annex_a_mo_library.json", "A"), ("annex_b_social_media.json", "B")):
            raw = (data_dir / fname).read_bytes()
            store.file_hashes[f"data/{fname}"] = sha256_bytes(raw)
            for rec in json.loads(raw)["records"]:
                store._add(_make(rec, annex))
        for rec in extra_records or []:
            store._add(_make(rec, "extra"))
        return store

    def _add(self, rec: SourceRecord) -> None:
        if rec.id in self.records:
            # A duplicate ID is itself suspicious (shadowing a trusted record).
            dup_id = f"{rec.id}#dup"
            rec = SourceRecord(**{**rec.__dict__, "id": dup_id, "quarantined": True,
                                  "flags": rec.flags + ("duplicate_id",)})
            self.records[dup_id] = rec
            return
        self.records[rec.id] = rec

    # --- queries -----------------------------------------------------------
    def exists(self, sid: str) -> bool:
        return sid in self.records

    def usable(self, sid: str) -> bool:
        r = self.records.get(sid)
        return r is not None and not r.quarantined

    def social(self) -> list[SourceRecord]:
        return [r for r in self.records.values() if r.annex in ("B", "extra")]

    def mos(self) -> list[SourceRecord]:
        return [r for r in self.records.values() if r.annex == "A" and not r.quarantined]

    def quarantined(self) -> list[SourceRecord]:
        return [r for r in self.records.values() if r.quarantined]
