from pathlib import Path
from typing import Dict, Literal, Optional, List
import logging
import yaml
from pydantic import BaseModel,Field

from dataclasses import dataclass

@dataclass
class SkillMetadata():
    license: str = None
    compatibility: str = None
    version: str = None
    allowed_tools: Optional[List[str]] = None
    metadata: Optional[dict] = None

    def to_dict(self):
        return {
            'license': self.license,
            'compatibility': self.compatibility,
            'version': self.version,
            'allowed_tools': self.allowed_tools,
            'metadata': self.metadata,
        }

      
@dataclass
class Skill():  
    name: str
    description: str
    body: str = ""
    path: Path = None
    metadata: SkillMetadata = None

    def to_config_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "path": str(self.path) if self.path else None,
        }


class SkillManager:
    def __init__(self, skill_dir: Path | str = None):
        self.skills: Dict[str, Skill] = {}
        self.skill_dir = skill_dir
        self._logger = logging.getLogger("skill.manager")
        if skill_dir is not None:
            self.add_skills(skill_dir)

    def add_skills(self, skill_dir: Path | str):
        added_skills = []
        for skill_path in skill_dir.iterdir():
            if not skill_path.is_dir():
                continue

            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            skill_data = self._parse_skill_md(skill_md)
            if skill_data:
                skill_name = skill_data['name']
                
                if skill_name in self.skills:
                    continue

                added_skills.append(skill_name)    
                self.skills[skill_name] = Skill(
                    name=skill_name,
                    description=skill_data['description'],
                    body=skill_data['body'],
                    state='Unknown',
                    path=skill_path,
                    metadata=skill_data['metadata']
                )

    def _parse_skill_md(self, skill_path: Path) -> Optional[Dict]:
        try:
            content = skill_path.read_text(encoding='utf-8')

            if not content.startswith('---'):
                return {
                    'name': skill_path.name,
                    'description': 'No description',
                    'body': content,
                    'metadata': SkillMetadata()
                }

            parts = content.split('---', 2)
            if len(parts) < 3:
                return {
                    'name': skill_path.name,
                    'description': 'Invalid format',
                    'body': content,
                    'metadata': SkillMetadata()
                }

            yaml_content = parts[1].strip()
            frontmatter = yaml.safe_load(yaml_content) or {}

            name = frontmatter.get('name', skill_path.name)
            description = frontmatter.get('description', '')
            if isinstance(description, str):
                description = description.strip()

            metadata = SkillMetadata(
                license=frontmatter.get('license'),
                compatibility=frontmatter.get('compatibility'),
                version=frontmatter.get('version'),
                metadata=frontmatter.get('metadata'),
                allowed_tools=frontmatter.get('allowed_tools')
            )

            body = parts[2].strip() if len(parts) > 2 else ""

            return {
                'name': name,
                'description': description,
                'body': body,
                'metadata': metadata
            }

        except Exception as e:
            self._logger.warning(f"Failed to parse skill file {skill_path}: {e}")
            return None
            
    def show_skill_detail(self, name: str):
        """show skill detail, the arg name is name of skill"""
        skill = self.skills.get(name)
        if skill:
            skill.state = 'Loaded'
            return skill.body
        else:
            return f"Skill {name} not found"

        