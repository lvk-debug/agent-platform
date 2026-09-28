"""
快捷提示词服务（工作助理的日常任务提示词）

两条来源：
- 内置（is_builtin=True, owner_id=None）：平台预置，所有用户可见，不可删除
- 自建（owner_id=用户 ID）：仅本人可见，可增删改

作用域规则：查询时返回「内置 ∪ 本人自建」，天然实现"全局共享 + 个人扩展"。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.hermes import HermesQuickPrompt
from app.utils.logger import logger


# 内置默认集：覆盖日常办公的高频场景
# icon 存 Ant Design 图标名，前端按需映射
BUILTIN_PROMPTS: List[Dict[str, Any]] = [
    {
        "title": "撰写周报",
        "description": "梳理本周进展，产出结构清晰的周报",
        "content": "请帮我整理本周的工作内容，生成一份结构清晰的周报，包含：本周完成事项、进行中的工作、遇到的问题与风险、下周计划。语言简洁，用要点呈现。",
        "icon": "FileTextOutlined",
        "category": "writing",
    },
    {
        "title": "会议纪要",
        "description": "把零散记录整理成结论明确的纪要",
        "content": "请把以下会议记录整理成一份会议纪要，包含：会议主题、关键结论、待办事项（含负责人与时间）、待决议问题。删除冗余口语，保留事实。",
        "icon": "TeamOutlined",
        "category": "writing",
    },
    {
        "title": "邮件起草",
        "description": "起草专业、简洁、得体的邮件",
        "content": "请帮我起草一封邮件。要求：主题明确，开头说明来意，正文分点陈述，结尾给出明确的期望回复或下一步动作。语气专业礼貌，控制在 300 字以内。",
        "icon": "MailOutlined",
        "category": "writing",
    },
    {
        "title": "代码审查",
        "description": "发现潜在问题并给出改进建议",
        "content": "请审查以下代码，指出：1）正确性或边界问题；2）性能隐患；3）可读性与可维护性改进点；4）安全风险。按严重程度排序，并给出具体修改建议。",
        "icon": "CodeOutlined",
        "category": "dev",
    },
    {
        "title": "数据整理",
        "description": "清洗数据并提炼关键结论",
        "content": "请帮我把这些数据整理成清晰的表格，并总结 3-5 条关键结论，指出异常值与趋势变化。若数据存在缺失或口径不一致，请明确说明。",
        "icon": "BarChartOutlined",
        "category": "analysis",
    },
    {
        "title": "文档摘要",
        "description": "长文档压缩为要点摘要",
        "content": "请为这篇文档生成要点摘要，控制在 200 字以内，保留核心结论与关键数据，使用分点呈现，不要加入原文之外的推测。",
        "icon": "FileSearchOutlined",
        "category": "analysis",
    },
    {
        "title": "方案对比",
        "description": "横向对比优劣并给出推荐",
        "content": "请对比以下几个方案，从成本、实施难度、可扩展性、风险四个维度分析，用表格呈现，最后给出明确推荐并说明理由。",
        "icon": "SwapOutlined",
        "category": "analysis",
    },
    {
        "title": "学习计划",
        "description": "制定可执行的分阶段学习计划",
        "content": "请为我制定一份可执行的学习计划，包含：阶段划分、每个阶段的目标与产出、推荐学习资源、每周投入时间建议，以及检验学习效果的方式。",
        "icon": "BookOutlined",
        "category": "productivity",
    },
]


class QuickPromptService:
    """快捷提示词服务"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_available(
        self, user_id: int, category: Optional[str] = None
    ) -> List[HermesQuickPrompt]:
        """列出可用提示词：内置 ∪ 本人自建"""
        query = self.db.query(HermesQuickPrompt).filter(
            HermesQuickPrompt.is_active.is_(True),
            or_(
                HermesQuickPrompt.is_builtin.is_(True),
                HermesQuickPrompt.owner_id == user_id,
            ),
        )
        if category:
            query = query.filter(HermesQuickPrompt.category == category)
        return query.order_by(
            HermesQuickPrompt.sort_order, HermesQuickPrompt.id
        ).all()

    def get(self, prompt_id: int) -> Optional[HermesQuickPrompt]:
        return (
            self.db.query(HermesQuickPrompt)
            .filter(HermesQuickPrompt.id == prompt_id)
            .first()
        )

    def get_owned(
        self, prompt_id: int, user_id: int
    ) -> Optional[HermesQuickPrompt]:
        """取本人可操作的提示词（内置提示词不属于任何人，返回 None）"""
        return (
            self.db.query(HermesQuickPrompt)
            .filter(
                HermesQuickPrompt.id == prompt_id,
                HermesQuickPrompt.owner_id == user_id,
            )
            .first()
        )

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        user_id: int,
        title: str,
        content: str,
        description: str = "",
        icon: str = "",
        category: str = "general",
        sort_order: int = 0,
    ) -> HermesQuickPrompt:
        prompt = HermesQuickPrompt(
            title=title,
            description=description,
            content=content,
            icon=icon,
            category=category,
            sort_order=sort_order,
            owner_id=user_id,
            is_builtin=False,
        )
        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)
        return prompt

    def update(self, prompt_id: int, **fields: Any) -> Optional[HermesQuickPrompt]:
        """更新本人提示词；自动忽略空值字段"""
        prompt = self.get(prompt_id)
        if not prompt:
            return None
        for key, value in fields.items():
            if value is not None and hasattr(prompt, key):
                setattr(prompt, key, value)
        self.db.commit()
        self.db.refresh(prompt)
        return prompt

    def delete(self, prompt_id: int, user_id: int) -> bool:
        """
        删除提示词。

        内置提示词不可删除（返回 False 由调用方转 400），避免误清空默认集。
        """
        prompt = self.get(prompt_id)
        if not prompt:
            return False
        if prompt.is_builtin:
            return False
        if prompt.owner_id != user_id:
            return False
        self.db.delete(prompt)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # 内置初始化
    # ------------------------------------------------------------------

    def init_builtin(self) -> int:
        """
        初始化内置默认集（按 title 去重，幂等）。

        Returns:
            本次新增的条数
        """
        existing = {
            p.title
            for p in self.db.query(HermesQuickPrompt)
            .filter(HermesQuickPrompt.is_builtin.is_(True))
            .all()
        }
        added = 0
        for index, item in enumerate(BUILTIN_PROMPTS):
            if item["title"] in existing:
                continue
            self.db.add(
                HermesQuickPrompt(
                    title=item["title"],
                    description=item["description"],
                    content=item["content"],
                    icon=item["icon"],
                    category=item["category"],
                    sort_order=index,
                    is_builtin=True,
                    owner_id=None,
                )
            )
            added += 1
        if added:
            self.db.commit()
            logger.info(f"初始化内置快捷提示词 {added} 条")
        return added


def get_quick_prompt_service(db: Session) -> QuickPromptService:
    """获取快捷提示词服务实例"""
    return QuickPromptService(db)
