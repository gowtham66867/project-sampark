from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sampark.core.models import Customer

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Skill:
    skill_id: str
    title: str
    match_patterns: list[str] = field(default_factory=list)
    body: str = ""
    requires_segment: Optional[str] = None
    requires_channel_condition: Optional[str] = None

    @property
    def is_customer_conditioned(self) -> bool:
        return bool(self.requires_segment or self.requires_channel_condition)


class SkillManager:
    """Hot-loads Markdown skill playbooks from sampark/skills/playbooks/ at
    construction time and pattern-matches an AgentAction.title to the
    single best-fit skill. The match key is a deterministic regex over the
    action title -- NOT an LLM call -- so skill selection stays cheap, fast,
    and fully testable offline. Skills shape ONLY the tone/framing an LLM
    uses to narrate an action; they never decide whether the action exists
    or is eligible (that remains planner.py / specialists.py / guardrails.py).
    """

    def __init__(self, playbooks_dir: Optional[Path] = None) -> None:
        self._dir = playbooks_dir or (Path(__file__).parent / "playbooks")
        self._skills: list[Skill] = self._load_skills()

    def _load_skills(self) -> list[Skill]:
        skills: list[Skill] = []
        if not self._dir.exists():
            return skills
        for path in sorted(self._dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            match = _FRONTMATTER_RE.match(text)
            if not match:
                continue
            frontmatter_raw, body = match.groups()
            frontmatter = self._parse_frontmatter(frontmatter_raw)
            skills.append(
                Skill(
                    skill_id=frontmatter.get("skill_id", path.stem),
                    title=frontmatter.get("title", path.stem),
                    match_patterns=frontmatter.get("match", []),
                    body=body.strip(),
                    requires_segment=frontmatter.get("requires_segment"),
                    requires_channel_condition=frontmatter.get("requires_channel_condition"),
                )
            )
        # Customer-attribute-conditioned skills (senior citizen, low
        # connectivity) are checked before generic title-only skills, so a
        # senior citizen's YONO onboarding gets the senior-citizen tone
        # rather than the generic PMJDY one.
        skills.sort(key=lambda skill: not skill.is_customer_conditioned)
        return skills

    @staticmethod
    def _parse_frontmatter(raw: str) -> dict[str, object]:
        """Tiny hand-rolled parser for the flat key: value / key: [list]
        shape used by these playbooks -- avoids adding pyyaml as a
        dependency for this file just to parse a handful of simple fields."""
        result: dict[str, object] = {}
        lines = raw.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith("#"):
                i += 1
                continue
            if ":" not in line:
                i += 1
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                result[key] = value.strip('"').strip("'")
                i += 1
            else:
                # Multi-line list: subsequent "  - item" lines.
                items: list[str] = []
                i += 1
                while i < len(lines) and lines[i].strip().startswith("-"):
                    items.append(lines[i].strip()[1:].strip().strip('"').strip("'"))
                    i += 1
                result[key] = items
        return result

    def select_skill(self, action_title: str, customer: Customer) -> Optional[Skill]:
        for skill in self._skills:
            title_matches = any(
                re.search(pattern, action_title, re.IGNORECASE)
                for pattern in skill.match_patterns
            )
            if not title_matches:
                continue
            if skill.requires_segment and skill.requires_segment.lower() not in customer.segment.lower():
                continue
            if (
                skill.requires_channel_condition
                and skill.requires_channel_condition not in customer.channel_conditions
            ):
                continue
            return skill
        return None

    def list_skills(self) -> list[str]:
        return [skill.skill_id for skill in self._skills]
