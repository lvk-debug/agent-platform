"""
数据库初始化种子数据
首次启动时自动创建默认管理员、模型供应商、模型和工具
"""

from datetime import UTC, datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.models.model import ModelProvider, Model
from app.models.tool import Tool
from app.models.hermes import HermesSkill
from app.models.support_business import (
    ReturnCategory,
    SupportOrder,
    SupportProduct,
    SupportReturnPolicy,
    SupportShipment,
)


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

    # ========== 工作助理内置技能 ==========
    if db.query(HermesSkill).count() == 0:
        skills = [
            HermesSkill(
                name="通用问答",
                slug="general-qa",
                description="直接、简洁地回答各类问题，适合日常咨询与知识查询",
                instruction="请使用简洁清晰的中文作答，先给结论再展开要点，避免冗长铺垫。",
                icon="💬",
                enabled=True,
                sort_order=10,
            ),
            HermesSkill(
                name="代码助手",
                slug="coding",
                description="编写、阅读与重构代码，输出可直接运行的完整示例",
                instruction="请以资深工程师标准作答：给出完整可运行代码、关键注释与边界情况说明，必要时补充使用示例。",
                icon="💻",
                enabled=True,
                sort_order=20,
            ),
            HermesSkill(
                name="数据分析",
                slug="data-analysis",
                description="对数据做清洗、统计与可视化，输出结论与建议",
                instruction="请先说明分析思路与口径，再给出计算过程、关键指标与可执行结论，数据不足时明确指出。",
                icon="📊",
                enabled=True,
                sort_order=30,
            ),
            HermesSkill(
                name="联网调研",
                slug="web-research",
                description="检索最新信息并交叉验证，标注信息来源",
                instruction="请优先使用联网搜索获取最新信息，对结论给出来源链接，并区分事实与推测。",
                icon="🔍",
                enabled=True,
                sort_order=40,
            ),
            HermesSkill(
                name="文档写作",
                slug="writing",
                description="撰写报告、方案与邮件，结构清晰、语气得体",
                instruction="请输出结构化文档：标题分级清晰，段落简短，必要时使用表格或要点列表，并控制语气专业克制。",
                icon="📝",
                enabled=True,
                sort_order=50,
            ),
        ]
        db.add_all(skills)
        db.commit()
        print(f"[seed] 创建 {len(skills)} 个工作助理内置技能")
    else:
        print("[seed] 工作助理技能已存在，跳过")

    # 客服业务示例数据（订单/物流/商品/退换货政策）
    seed_support_business(db)

    print("[seed] 数据库初始化完成")


def seed_support_business(db: Session) -> None:
    """初始化客服业务示例数据（订单/物流/商品/退换货政策），各表为空时才写入"""
    if db.query(SupportOrder).count() == 0:
        orders = [
            SupportOrder(order_no="ORD-001", customer_name="张伟", product="智能蓝牙耳机 Pro", amount=299.00, status="shipped", ordered_at=datetime(2026, 5, 1, tzinfo=UTC)),
            SupportOrder(order_no="ORD-002", customer_name="李娜", product="无线充电板", amount=89.00, status="processing", ordered_at=datetime(2026, 5, 5, tzinfo=UTC)),
            SupportOrder(order_no="ORD-003", customer_name="王芳", product="机械键盘 K8", amount=459.00, status="delivered", ordered_at=datetime(2026, 4, 20, tzinfo=UTC)),
        ]
        db.add_all(orders)
        db.commit()
        print("[seed] 创建 3 条示例订单")

    if db.query(SupportProduct).count() == 0:
        products = [
            SupportProduct(product_no="P001", name="智能蓝牙耳机 Pro", price=299.0, warranty="12 个月", category=ReturnCategory.ELECTRONICS, description="主动降噪、30 小时续航、IPX5 防水、蓝牙 5.3。", features=["降噪", "30 小时续航", "IPX5 防水", "蓝牙 5.3"]),
            SupportProduct(product_no="P002", name="无线充电板", price=89.0, warranty="6 个月", category=ReturnCategory.ELECTRONICS, description="15W 快充、Qi 协议、LED 指示、过温保护。", features=["15W 快充", "Qi 协议", "LED 指示", "过温保护"]),
            SupportProduct(product_no="P003", name="机械键盘 K8", price=459.0, warranty="12 个月", category=ReturnCategory.ELECTRONICS, description="87 键紧凑布局、热插拔轴体、RGB 背光、Type-C 接口。", features=["87 键", "热插拔", "RGB 背光", "Type-C"]),
        ]
        db.add_all(products)
        db.commit()
        print("[seed] 创建 3 条示例商品")

    if db.query(SupportShipment).count() == 0:
        shipments = [
            SupportShipment(order_no="ORD-001", carrier="顺丰快递", tracking_no="SF1234567890", current_location="上海市分拣中心", estimated_text="明天", status="运输中"),
            SupportShipment(order_no="ORD-002", carrier="中通快递", tracking_no="ZT9876543210", current_location="已出库", estimated_text="3 天后", status="待揽收"),
        ]
        db.add_all(shipments)
        db.commit()
        print("[seed] 创建 2 条示例物流")

    if db.query(SupportReturnPolicy).count() == 0:
        policies = [
            SupportReturnPolicy(category=ReturnCategory.ELECTRONICS, category_label=ReturnCategory.LABELS[ReturnCategory.ELECTRONICS], policy_content="电子类产品支持签收后 7 天内无理由退货（需保持原包装、配件与说明书完整）；自收货起提供 12 个月质保，非人为损坏免费维修，人为损坏收取成本费。"),
            SupportReturnPolicy(category=ReturnCategory.CLOTHING, category_label=ReturnCategory.LABELS[ReturnCategory.CLOTHING], policy_content="服装类在吊牌完整、未水洗未穿着的情况下支持 15 天内退换；尺码不合可免费换货一次，往返运费由买家承担。"),
            SupportReturnPolicy(category=ReturnCategory.BOOKS, category_label=ReturnCategory.LABELS[ReturnCategory.BOOKS], policy_content="图书类除印刷/装订质量问题外不支持无理由退货；如收到破损、缺页可拍照申请换货，运费由商家承担。"),
        ]
        db.add_all(policies)
        db.commit()
        print("[seed] 创建 3 条示例退换货政策")
