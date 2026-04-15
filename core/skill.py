from pathlib import Path
from typing import Dict, Literal, Optional, List
import yaml
from pydantic import BaseModel,Field


class SkillMetadata(BaseModel):
    license: Optional[str] = Field(default=None, description="技能授权协议")
    compatibility: Optional[str] = Field(default=None, description="技能兼容性")
    version: Optional[str] = Field(default=None, description="技能版本")
    allowed_tools: Optional[List[str]] = Field(default=None, description="允许的工具列表")
    metadata: Optional[dict] = Field(default=None, description="技能元数据")
      

class Skill(BaseModel):
    name: str
    description: str
    body: str = Field(description="技能的原始文档内容")
    state: Literal['Unknown', 'Known', 'Loaded'] = Field(default='Unknown', description="表示技能是否已加载至模型")
    path: Path = Field(description="技能目录路径")
    metadata: SkillMetadata = Field(default_factory=SkillMetadata, description="技能元数据")


class SkillManager:
    def __init__(self, base_dir: Path | str, skill_dir: Path | str = None):
        self.base_dir = base_dir
        self.skills: Dict[str, Skill] = {}
        self.skill_dir = skill_dir      
        if skill_dir is not None:
            self.add_skills(skill_dir)

    def _validate_path(self, path: Path | str, base_dir: Path | str) -> bool:
        if not isinstance(path, Path):
           path = Path(path)

        if not path.is_relative_to(base_dir):
            raise ValueError(f"路径 '{path}' 超出基础目录 '{base_dir}' 范围")
        
        if not path.exists():
            raise FileNotFoundError(f"路径不存在: {path}")
        
        if not path.is_dir():
            raise NotADirectoryError(f"路径不是目录: {path}")
        
        return path

    def add_skills(self, skill_dir: Path | str):
        skill_dir = self._validate_path(skill_dir, self.base_dir)
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
        print(f"Added skills: {added_skills}")

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
                description = description.strip().split('\n')[0]

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
            return None
          
    def get_skills_state(self) -> Dict[str, Literal['Unknown', 'Known', 'Loaded']]:
        return {name: s.state for name, s in self.skills.items()}

    def show_skills(self):
        message = ['Available skills:\n']
        for skill_name, skill in self.skills.items():
            if skill.state == 'Unknown':
                message.append(f"{skill_name}: {skill.description}")
                skill.state = 'Known'
        return '\n'.join(message)
    
    def show_skill_detail(self, name: str):
        """show skill detail, the arg name is name of skill"""
        skill = self.skills.get(name)
        if skill:
            skill.state = 'Loaded'
            return skill.body
        else:
            return f"Skill {name} not found"


if __name__ == "__main__":
    skill_manager = SkillManager(Path("./skills"), Path("./"))
    skill_manager.show_skills()
    skill_manager.show_skill_detail("frontend-dev")
    print(skill_manager.get_skills_state())
        