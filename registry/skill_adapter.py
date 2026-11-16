"""
Skill Adapter and Procedural Registry for Operation Jarvis.
Discovers and indexes agent-skills, superpowers, anthropic-skills, ui-ux-pro-max,
understand-anything, ponytail, and builtin skills from canonical markdown definitions.
"""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from config.settings import settings

class SkillInfo:
    def __init__(self, name: str, description: str, path: Path, content: str, source_plugin: str = "custom", compatibility: str = "both"):
        self.name = name
        self.description = description
        self.path = path
        self.content = content
        self.source_plugin = source_plugin
        self.compatibility = compatibility  # "antigravity", "jarvis", "both"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
            "source_plugin": self.source_plugin,
            "compatibility": self.compatibility
        }

class SkillRegistry:
    def __init__(self):
        self.skills: Dict[str, SkillInfo] = {}
        self.discover_skills()

    def discover_skills(self):
        self.skills.clear()

        # 1. Discover skills from installed plugins in .gemini/config/plugins
        plugins_root = getattr(settings, "plugins_dir", Path(r"C:\Users\Akshay aravind .rv\.gemini\config\plugins"))
        if plugins_root.exists():
            for plugin_dir in plugins_root.iterdir():
                if not plugin_dir.is_dir():
                    continue
                plugin_name = plugin_dir.name
                # Check for SKILL.md recursively within this plugin
                for skill_md in plugin_dir.rglob("SKILL.md"):
                    # Folder holding this SKILL.md
                    folder = skill_md.parent
                    # Avoid nested references or test folders if named tests
                    if "tests" in folder.parts or "node_modules" in folder.parts or ".git" in folder.parts:
                        continue
                    self._load_skill(folder.name, skill_md, source_plugin=plugin_name)

        # 2. Discover builtin Antigravity skills
        builtin_dir = getattr(settings, "builtin_skills_dir", Path(r"C:\Users\Akshay aravind .rv\.gemini\antigravity-cli\builtin\skills"))
        if builtin_dir.exists():
            for item in builtin_dir.iterdir():
                if item.is_dir():
                    skill_md = item / "SKILL.md"
                    if skill_md.exists():
                        self._load_skill(item.name, skill_md, source_plugin="builtin")

    def _load_skill(self, default_name: str, md_path: Path, source_plugin: str):
        try:
            with open(md_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()

            name = default_name
            description = ""

            # Check for YAML frontmatter
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
                    desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
                    if name_match:
                        name = name_match.group(1).strip().strip('"\'')
                    if desc_match:
                        # multi-line or single-line description
                        description = desc_match.group(1).strip().strip('"\'')

            if not description:
                # First non-empty paragraph after headers
                lines = [line.strip() for line in raw.splitlines() if line.strip() and not line.startswith("#")]
                description = lines[0] if lines else f"Skill provided by {source_plugin}."

            # Clean name if duplicated
            if name in self.skills:
                # Prefix with plugin name if conflicting
                unique_key = f"{source_plugin}:{name}"
            else:
                unique_key = name

            self.skills[unique_key] = SkillInfo(
                name=unique_key,
                description=description,
                path=md_path,
                content=raw,
                source_plugin=source_plugin,
                compatibility="both"
            )
        except Exception:
            pass

    def list_skills(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self.skills.values()]

    def get_skill(self, name: str) -> Optional[SkillInfo]:
        if name in self.skills:
            return self.skills[name]
        # Search by suffix if qualified
        for k, v in self.skills.items():
            if k == name or k.endswith(f":{name}"):
                return v
        return None

    def find_relevant_skills(self, objective: str, max_count: int = 3) -> List[SkillInfo]:
        obj_lower = objective.lower()
        scored = []
        for s in self.skills.values():
            score = 0
            # Name match
            words = s.name.replace("-", " ").replace(":", " ").lower().split()
            for w in words:
                if len(w) > 3 and w in obj_lower:
                    score += 3
            # Description match
            desc_words = s.description.lower().split()
            for w in desc_words:
                if len(w) > 4 and w in obj_lower:
                    score += 1
            if score > 0:
                scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:max_count]]

    def count_by_source(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for s in self.skills.values():
            counts[s.source_plugin] = counts.get(s.source_plugin, 0) + 1
        return counts

skill_registry = SkillRegistry()
