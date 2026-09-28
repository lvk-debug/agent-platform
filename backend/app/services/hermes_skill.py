"""
Hermes 技能服务

职责：
1. 技能（HermesSkill）的 CRUD
2. 按 slug 批量解析技能指令，供对话注入使用

技能是平台自建元数据，不影响 Hermes 服务端配置：
选中后仅以 system 指令形式叠加到本次对话（Hermes 会保留全部内置能力）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.hermes import HermesSkill
from app.utils.logger import logger


class HermesSkillService:
    """技能 CRUD 服务"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== 查询 ====================

    def list_skills(
        self, keyword: str = "", enabled_only: bool = False
    ) -> List[HermesSkill]:
        """
        列出技能

        Args:
            keyword: 名称/标识/描述模糊匹配
            enabled_only: 只返回启用中的技能
        """
        query = self.db.query(HermesSkill)
        if enabled_only:
            query = query.filter(HermesSkill.enabled.is_(True))
        if keyword:
            pattern = f"%{keyword}%"
            query = query.filter(
                HermesSkill.name.like(pattern)
                | HermesSkill.slug.like(pattern)
                | HermesSkill.description.like(pattern)
            )
        return query.order_by(HermesSkill.sort_order.asc(), HermesSkill.created_at).all()

    def get_skill(self, skill_id: str) -> Optional[HermesSkill]:
        """按主键获取技能"""
        return self.db.query(HermesSkill).filter(HermesSkill.id == skill_id).first()

    def get_by_slug(self, slug: str) -> Optional[HermesSkill]:
        """按唯一标识获取技能"""
        return self.db.query(HermesSkill).filter(HermesSkill.slug == slug).first()

    # ==================== 写入 ====================

    def create_skill(
        self,
        name: str,
        slug: str,
        description: str = "",
        instruction: str = "",
        icon: str = "",
        enabled: bool = True,
        sort_order: int = 0,
        created_by: Optional[int] = None,
    ) -> HermesSkill:
        """创建技能（slug 需唯一）"""
        skill = HermesSkill(
            name=name,
            slug=slug,
            description=description,
            instruction=instruction,
            icon=icon,
            enabled=enabled,
            sort_order=sort_order,
            created_by=created_by,
        )
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        logger.info(f"创建技能: {slug}")
        return skill

    def update_skill(self, skill_id: str, **fields) -> Optional[HermesSkill]:
        """更新技能字段（只更新传入的非 None 字段）"""
        skill = self.get_skill(skill_id)
        if not skill:
            return None
        for key, value in fields.items():
            if value is not None and hasattr(skill, key):
                setattr(skill, key, value)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        skill = self.get_skill(skill_id)
        if not skill:
            return False
        self.db.delete(skill)
        self.db.commit()
        logger.info(f"删除技能: {skill.slug}")
        return True

    # ==================== 对话注入 ====================

    def resolve_instructions(self, slugs: List[str]) -> List[Dict[str, str]]:
        """
        按 slug 解析出技能名称与指令（保持传入顺序，跳过不存在/停用的技能）

        Returns:
            [{"name": "代码助手", "instruction": "..."}]
        """
        if not slugs:
            return []
        skills = (
            self.db.query(HermesSkill)
            .filter(HermesSkill.slug.in_(slugs), HermesSkill.enabled.is_(True))
            .all()
        )
        by_slug = {s.slug: s for s in skills}
        return [
            {"name": by_slug[slug].name, "instruction": by_slug[slug].instruction or ""}
            for slug in slugs
            if slug in by_slug
        ]


def get_hermes_skill_service(db: Session) -> HermesSkillService:
    """获取技能服务实例"""
    return HermesSkillService(db)
