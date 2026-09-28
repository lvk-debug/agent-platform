"""
Paper Agent 服务包

论文研读与综述助手：检索论文 → 排序 → 生成可追溯的 Markdown 综述。

当前实现里程碑1（arXiv 检索 + 综述），M2-M4 已在 tools.py 预留接口。
"""

from app.services.paper_agent.service import PaperAgentService, get_paper_agent_service
from app.services.paper_agent.tools import PaperMetadata

__all__ = [
    "PaperAgentService",
    "PaperMetadata",
    "get_paper_agent_service",
]
