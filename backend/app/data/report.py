"""Structured reporting for the ingestion + validation pipeline.

Nothing is discarded silently: every dropped or altered record is counted and
categorized here, and the report is written to
``data/processed/_reports/*.json`` and printed to the console.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class RejectionBucket:
    """One reason records were dropped, with a few examples."""

    reason: str
    count: int = 0
    examples: list[str] = field(default_factory=list)

    def add(self, example: str) -> None:
        self.count += 1
        if len(self.examples) < 5:
            self.examples.append(str(example)[:200])


@dataclass
class StageReport:
    """Per-source (or per-stage) outcome."""

    name: str
    available: bool = True
    note: str = ""
    input_rows: int = 0
    output_rows: int = 0
    rejections: dict[str, RejectionBucket] = field(default_factory=dict)

    def reject(self, reason: str, example: str) -> None:
        self.rejections.setdefault(reason, RejectionBucket(reason=reason)).add(example)

    @property
    def rejected_total(self) -> int:
        return sum(b.count for b in self.rejections.values())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "available": self.available,
            "note": self.note,
            "input_rows": self.input_rows,
            "output_rows": self.output_rows,
            "rejected_total": self.rejected_total,
            "rejections": {k: asdict(v) for k, v in self.rejections.items()},
        }


@dataclass
class QualityCheck:
    name: str
    passed: bool
    detail: str = ""
    severity: str = "error"  # "error" | "warning"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PipelineReport:
    kind: str  # "ingestion" | "validation"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None
    stages: list[StageReport] = field(default_factory=list)
    checks: list[QualityCheck] = field(default_factory=list)
    dataset_counts: dict[str, int] = field(default_factory=dict)
    entity_counts: dict[str, int] = field(default_factory=dict)

    def add_stage(self, stage: StageReport) -> StageReport:
        self.stages.append(stage)
        return stage

    def add_check(self, check: QualityCheck) -> None:
        self.checks.append(check)

    @property
    def hard_failures(self) -> list[QualityCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.hard_failures

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "ok": self.ok,
            "dataset_counts": self.dataset_counts,
            "entity_counts": self.entity_counts,
            "stages": [s.to_dict() for s in self.stages],
            "checks": [c.to_dict() for c in self.checks],
        }

    def write(self, path: Path) -> None:
        self.finished_at = datetime.now(UTC).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    def render(self) -> str:
        lines: list[str] = [f"== {self.kind} report =="]
        if self.entity_counts:
            lines.append("entities: " + ", ".join(f"{k}={v}" for k, v in self.entity_counts.items()))
        if self.dataset_counts:
            lines.append("datasets:")
            lines += [f"  {k:<20} {v:>8}" for k, v in self.dataset_counts.items()]
        if self.stages:
            lines.append("stages:")
            for s in self.stages:
                status = "ok" if s.available else "UNAVAILABLE"
                lines.append(
                    f"  {s.name:<16} {status:<12} in={s.input_rows} out={s.output_rows} "
                    f"rejected={s.rejected_total}"
                )
                for b in s.rejections.values():
                    lines.append(f"      - {b.reason}: {b.count}")
                if s.note:
                    lines.append(f"      note: {s.note}")
        if self.checks:
            lines.append("quality checks:")
            for c in self.checks:
                mark = "PASS" if c.passed else ("WARN" if c.severity == "warning" else "FAIL")
                lines.append(f"  [{mark}] {c.name}{(' - ' + c.detail) if c.detail else ''}")
        lines.append(f"result: {'OK' if self.ok else 'FAILED'}")
        return "\n".join(lines)
