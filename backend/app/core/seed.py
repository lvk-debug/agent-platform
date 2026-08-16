"""
数据库初始化种子数据
首次启动时自动创建默认管理员、模型供应商、模型和工具
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.models.model import ModelProvider, Model
from app.models.tool import Tool


def seed_data(db: Session) -> None:
    """
    初始化默认数据（仅在数据库为空时执行）
    """
    # ========== 默认管理员 ==========
    if db.query(User).count() == 0:
        admin_password = getattr(settings, "ADMIN_PASSWORD", None) or "admin123"
        admin = User(
            email="admin@agentplatform.com",
            username="admin",
            hashed_password=get_password_hash(admin_password),
            full_name="管理员",
            is_active=True,
            is_superuser=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"[seed] 创建默认管理员: admin / {admin_password}")
    else:
        admin = db.query(User).filter(User.is_superuser == True).first()

    # ========== 模型供应商 ==========
    if db.query(ModelProvider).count() == 0:
        providers = [
            ModelProvider(
                name="OpenAI",
                provider_type="openai",
                api_endpoint=settings.OPENAI_API_BASE,
                api_key=settings.OPENAI_API_KEY or None,
                is_active=True,
            ),
            ModelProvider(
                name="Anthropic",
                provider_type="anthropic",
                api_endpoint="https://api.anthropic.com",
                api_key=settings.ANTHROPIC_API_KEY or None,
                is_active=True,
            ),
            ModelProvider(
                name="本地模型 (Ollama)",
                provider_type="local",
                api_endpoint=settings.LOCAL_LLM_BASE_URL,
                is_active=True,
            ),
        ]
        db.add_all(providers)
        db.commit()
        for p in providers:
            db.refresh(p)
        print(f"[seed] 创建 {len(providers)} 个模型供应商")

        # ========== 默认模型 ==========
        openai_provider = providers[0]
        anthropic_provider = providers[1]
        local_provider = providers[2]

        models = [
            # OpenAI
            Model(
                provider_id=openai_provider.id,
                name="GPT-4o",
                model_id="gpt-4o",
                description="OpenAI 旗舰多模态模型，支持文本和图像输入",
                max_tokens=128000,
                supports_streaming=True,
                supports_function_calling=True,
                default_temperature=70,
                default_max_tokens=4096,
                is_active=True,
            ),
            Model(
                provider_id=openai_provider.id,
                name="GPT-4o Mini",
                model_id="gpt-4o-mini",
                description="轻量快速模型，适合简单任务",
                max_tokens=128000,
                supports_streaming=True,
                supports_function_calling=True,
                default_temperature=70,
                default_max_tokens=4096,
                is_active=True,
            ),
            # Anthropic
            Model(
                provider_id=anthropic_provider.id,
                name="Claude Sonnet 4",
                model_id="claude-sonnet-4-20250514",
                description="平衡性能与速度的 Claude 模型",
                max_tokens=200000,
                supports_streaming=True,
                supports_function_calling=True,
                default_temperature=70,
                default_max_tokens=4096,
                is_active=True,
            ),
            Model(
                provider_id=anthropic_provider.id,
                name="Claude Haiku 4",
                model_id="claude-haiku-4-20250514",
                description="快速轻量的 Claude 模型",
                max_tokens=200000,
                supports_streaming=True,
                supports_function_calling=True,
                default_temperature=70,
                default_max_tokens=4096,
                is_active=True,
            ),
            # 本地模型
            Model(
                provider_id=local_provider.id,
                name="Llama 3",
                model_id="llama3",
                description="Meta 开源大语言模型，本地部署",
                max_tokens=8192,
                supports_streaming=True,
                supports_function_calling=False,
                default_temperature=70,
                default_max_tokens=2048,
                is_active=True,
            ),
        ]
        db.add_all(models)
        db.commit()
        print(f"[seed] 创建 {len(models)} 个默认模型")
    else:
        print("[seed] 模型供应商已存在，跳过")

    # ========== 内置工具 ==========
    if db.query(Tool).count() == 0:
        tools = [
            Tool(
                name="web_search",
                description="搜索互联网获取实时信息",
                tool_type="builtin",
                icon="SearchOutlined",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"],
                },
                return_schema={
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "url": {"type": "string"},
                                    "snippet": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                is_active=True,
            ),
            Tool(
                name="web_browse",
                description="访问并读取指定网页内容",
                tool_type="builtin",
                icon="GlobalOutlined",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "网页URL"}
                    },
                    "required": ["url"],
                },
                return_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "url": {"type": "string"},
                    },
                },
                is_active=True,
            ),
            Tool(
                name="code_interpreter",
                description="在沙箱中执行 Python 代码",
                tool_type="builtin",
                icon="CodeOutlined",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python代码"}
                    },
                    "required": ["code"],
                },
                return_schema={
                    "type": "object",
                    "properties": {
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "result": {"type": "string"},
                    },
                },
                is_active=True,
            ),
            Tool(
                name="knowledge_retrieval",
                description="从知识库中检索相关文档片段",
                tool_type="builtin",
                icon="DatabaseOutlined",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "检索查询"},
                        "knowledge_base_id": {
                            "type": "integer",
                            "description": "知识库ID",
                        },
                    },
                    "required": ["query"],
                },
                return_schema={
                    "type": "object",
                    "properties": {
                        "segments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "content": {"type": "string"},
                                    "score": {"type": "number"},
                                    "document_name": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                is_active=True,
            ),
        ]
        db.add_all(tools)
        db.commit()
        print(f"[seed] 创建 {len(tools)} 个内置工具")
    else:
        print("[seed] 工具已存在，跳过")

    print("[seed] 数据库初始化完成")
