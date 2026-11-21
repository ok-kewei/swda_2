"""Loads versioned configuration and records a hash of each file for the trace."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), sha256_bytes(raw)


@dataclass(frozen=True)
class ActorProfile:
    id: str
    display_name: str
    kind: str
    goals: tuple[str, ...]
    capabilities: frozenset[str]
    private_knowledge: tuple[str, ...]
    cannot_see: tuple[str, ...]
    visible_sources: tuple[str, ...]  # "*" means all non-quarantined sources
    allowed_tools: frozenset[str]
    may_message: frozenset[str]

    def can_see(self, source_id: str) -> bool:
        return "*" in self.visible_sources or source_id in self.visible_sources


@dataclass(frozen=True)
class Limits:
    max_rounds: int
    max_messages_per_agent_per_round: int
    max_message_chars: int
    max_llm_calls: int
    max_retries: int
    max_cost_usd: float
    usd_per_1k_tokens: float


@dataclass
class Config:
    profiles: dict[str, ActorProfile]
    functions: dict[str, str]
    behaviour_tags: frozenset[str]
    flow_assets: frozenset[str]
    flow_parties: frozenset[str]
    mo_tags: dict[str, frozenset[str]]
    mo_tag_version: str
    variation_min_coverage: float
    limits: Limits
    data_dir: Path
    file_hashes: dict[str, str] = field(default_factory=dict)

    @property
    def actor_ids(self) -> list[str]:
        return [p.id for p in self.profiles.values() if p.kind == "actor"]


def load_config(root: Path = REPO_ROOT, limits_override: dict | None = None) -> Config:
    cfg_dir = root / "config"
    actors, h_actors = _load(cfg_dir / "actors.json")
    taxonomy, h_tax = _load(cfg_dir / "taxonomy.json")
    mo_tags, h_mo = _load(cfg_dir / "mo_feature_tags.json")
    limits, h_lim = _load(cfg_dir / "limits.json")
    if limits_override:
        limits = {**limits, **limits_override}

    profiles: dict[str, ActorProfile] = {}
    for aid, p in actors["actors"].items():
        unknown = set(p["capabilities"]) - set(taxonomy["functions"])
        if unknown:
            raise ValueError(f"actor {aid} has unknown capabilities {unknown}")
        profiles[aid] = ActorProfile(
            id=aid,
            display_name=p["display_name"],
            kind=p["kind"],
            goals=tuple(p["goals"]),
            capabilities=frozenset(p["capabilities"]),
            private_knowledge=tuple(p["private_knowledge"]),
            cannot_see=tuple(p["cannot_see"]),
            visible_sources=tuple(p["visible_sources"]),
            allowed_tools=frozenset(p["allowed_tools"]),
            may_message=frozenset(p["may_message"]),
        )

    tags = frozenset(taxonomy["behaviour_tags"])
    for mo, t in mo_tags["mo_tags"].items():
        if set(t) - tags:
            raise ValueError(f"{mo} uses tags outside the taxonomy: {set(t) - tags}")

    return Config(
        profiles=profiles,
        functions=dict(taxonomy["functions"]),
        behaviour_tags=tags,
        flow_assets=frozenset(taxonomy["flow_assets"]),
        flow_parties=frozenset(taxonomy["flow_parties"]),
        mo_tags={k: frozenset(v) for k, v in mo_tags["mo_tags"].items()},
        mo_tag_version=mo_tags["version"],
        variation_min_coverage=float(mo_tags["thresholds"]["variation_min_coverage"]),
        limits=Limits(**{k: limits[k] for k in Limits.__dataclass_fields__}),
        data_dir=root / "data",
        file_hashes={
            "config/actors.json": h_actors,
            "config/taxonomy.json": h_tax,
            "config/mo_feature_tags.json": h_mo,
            "config/limits.json": h_lim,
        },
    )
