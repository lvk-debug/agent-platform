"""
聊天助手服务 — 配置管理、对话处理、知识库检索集成
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.app import App
from app.models.user import User
from app.schemas.chatbot import (
    ChatRequest,
    ChatResponse,
    ChatbotConfig,
    ChatbotPromptConfig,
    ChatbotUpdate,
    ConversationResponse,
    KnowledgeBaseConfig,
    MessageResponse,
)
from app.services.knowledge import get_knowledge_service
from app.services.llm import LLMService
from app.utils.logger import logger


class ChatbotService:
    """
    聊天助手服务
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 配置管理
    # ------------------------------------------------------------------

    def get_chatbot_config(self, app_id: int) -> Optional[ChatbotConfig]:
        """获取聊天助手配置"""
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return None

        config_data = app.config or {}
        logger.info(f"加载配置: app_id={app_id}, 知识库数量: {len(config_data.get('knowledge_bases', []))}")
        return ChatbotConfig(**config_data)

    def update_chatbot_config(
        self, app_id: int, update: ChatbotUpdate
    ) -> Optional[App]:
        """更新聊天助手配置"""
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return None

        if update.name is not None:
            app.name = update.name
        if update.description is not None:
            app.description = update.description
        if update.config is not None:
            # 合并配置
            current_config = app.config or {}
            new_config = update.config.model_dump()
            current_config.update(new_config)
            app.config = current_config

        app.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(app)
        return app

    def save_chatbot_config(self, app_id: int, config: ChatbotConfig) -> bool:
        """保存完整配置"""
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return False

        config_dict = config.model_dump()
        logger.info(f"保存配置: app_id={app_id}, 知识库数量: {len(config_dict.get('knowledge_bases', []))}")
        app.config = config_dict
        app.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # 对话处理
    # ------------------------------------------------------------------

    async def chat(
        self,
        app_id: int,
        request: ChatRequest,
        user: User,
    ) -> ChatResponse:
        """
        处理聊天请求

        流程:
        1. 获取配置
        2. 变量替换
        3. 知识库检索（如有）
        4. 构建消息
        5. 调用 LLM
        6. 返回结果
        """
        config = self.get_chatbot_config(app_id)
        if not config:
            raise ValueError("应用配置不存在")

        logger.info(f"聊天请求: app_id={app_id}, 知识库数量: {len(config.knowledge_bases) if config.knowledge_bases else 0}")

        # 1. 变量替换
        query = request.query
        if request.inputs:
            query = self._replace_variables(query, request.inputs, config)

        # 2. 检索前增强：Query 扩展 → HyDE
        search_query = query
        if config.knowledge_bases:
            # 2a. Query 扩展
            if config.query_expansion_enabled:
                expanded = await self._expand_query(query, config)
                if expanded:
                    search_query = expanded
                    logger.info(f"查询扩展: '{query[:50]}' → '{search_query[:50]}'")

            # 2b. HyDE 假设性文档
            if config.hyde_enabled:
                hyde_text = await self._generate_hyde(query, config)
                if hyde_text:
                    search_query = hyde_text
                    logger.info(f"HyDE 生成: '{hyde_text[:80]}'")

        # 3. 知识库检索
        context_text = ""
        citations: List[Dict[str, Any]] = []
        if config.knowledge_bases:
            context_text, citations = await self._retrieve_knowledge(
                config.knowledge_bases, search_query
            )

        # 3. 获取或创建会话
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = self._create_conversation(app_id, user.id, query)

        # 4. 保存用户消息
        self._save_message(conversation_id, "user", query)

        # 5. 构建消息列表
        messages = self._build_messages(
            config, query, context_text, conversation_id
        )

        # 6. 调用 LLM
        try:
            # 尝试从配置获取模型信息
            logger.info(f"开始调用 LLM, model_id={config.model_id}")
            if config.model_id:
                from app.models.model import Model
                model = self.db.query(Model).filter(Model.id == config.model_id).first()
                logger.info(f"找到模型: {model}, 供应商: {model.provider if model else None}")
                if model and model.provider:
                    provider_config = model.provider
                    from app.services.llm import LLMService
                    llm_service = LLMService()
                    # 注册供应商
                    await llm_service.register_provider(
                        provider_type=provider_config.provider_type,
                        api_key=provider_config.api_key,
                        api_endpoint=provider_config.api_endpoint,
                    )
                    # 获取模型参数
                    params = config.model_parameters
                    logger.info(f"调用 LLM: model={model.model_id}, provider={provider_config.provider_type}, temp={params.temperature if params else 0.7}")
                    response = await llm_service.chat(
                        messages=messages,
                        model=model.model_id,  # 使用 model_id 而不是 name
                        provider=provider_config.provider_type,
                        temperature=params.temperature if params else 0.7,
                        max_tokens=params.max_tokens if params else 2048,
                        top_p=params.top_p if params else 1.0,
                    )
                    answer = response.get("content", "")
                else:
                    logger.warning(f"模型 {config.model_id} 或其供应商不存在")
                    answer = self._generate_demo_response(query, context_text)
            else:
                # 没有配置模型，使用演示模式
                logger.info("未配置模型，使用演示模式")
                answer = self._generate_demo_response(query, context_text)
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}", exc_info=True)
            # 降级到演示模式
            answer = self._generate_demo_response(query, context_text)

        # 7. 保存助手回复
        message_id = self._save_message(conversation_id, "assistant", answer)

        return ChatResponse(
            answer=answer,
            conversation_id=conversation_id,
            message_id=message_id,
            metadata={
                "model": config.model_name,
                "knowledge_context": context_text[:500] if context_text else None,
                "citations": citations if citations else None,
            },
        )

    def _replace_variables(
        self,
        text: str,
        inputs: Dict[str, str],
        config: ChatbotConfig,
    ) -> str:
        """替换文本中的变量"""
        for var in config.variables:
            if var.key in inputs:
                text = text.replace("{{" + var.key + "}}", inputs[var.key])
        return text

    # ------------------------------------------------------------------
    # 检索增强：Query 扩展 & HyDE
    # ------------------------------------------------------------------

    DEFAULT_EXPANSION_PROMPT = """你是一个查询扩展助手。请将用户的问题扩展为更适合全文检索的形式。

规则：
1. 保留原始问题的核心语义
2. 补充相关的同义词、近义词、神学术语
3. 输出 1-3 个扩展后的检索查询，每行一个
4. 不要输出解释，只输出查询

用户问题：{query}"""

    DEFAULT_HYDE_PROMPT = """你是一个假设性文档生成器。请根据用户的问题，生成一段假想的文档内容（200-400字），这段内容应该：
1. 假设是知识库中真实存在的一篇文章
2. 直接回答或解释用户的问题
3. 使用陈述语气，不要用疑问句
4. 包含具体的细节和信息

用户问题：{query}

假想文档："""

    async def _call_llm_for_retrieval(self, prompt: str, config: ChatbotConfig) -> Optional[str]:
        """调用 LLM 生成检索增强文本（复用配置的模型）"""
        if not config.model_id:
            return None

        try:
            from app.models.model import Model
            model = self.db.query(Model).filter(Model.id == config.model_id).first()
            if not model or not model.provider:
                return None

            provider_config = model.provider
            llm_service = LLMService()
            await llm_service.register_provider(
                provider_type=provider_config.provider_type,
                api_key=provider_config.api_key,
                api_endpoint=provider_config.api_endpoint,
            )

            response = await llm_service.chat(
                messages=[{"role": "user", "content": prompt}],
                model=model.model_id,
                provider=provider_config.provider_type,
                temperature=0.3,
                max_tokens=512,
            )
            return response.get("content", "").strip()
        except Exception as e:
            logger.warning(f"检索增强 LLM 调用失败: {e}")
            return None

    async def _expand_query(self, query: str, config: ChatbotConfig) -> Optional[str]:
        """
        Query 扩展：用 LLM 将用户问题扩展为多个相关表述

        返回扩展后的查询文本（多行拼接），用于检索
        """
        prompt_template = config.query_expansion_prompt or self.DEFAULT_EXPANSION_PROMPT
        prompt = prompt_template.replace("{query}", query)

        result = await self._call_llm_for_retrieval(prompt, config)
        if not result:
            return None

        # 取第一行作为主查询，其余作为补充
        lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
        if not lines:
            return None

        # 用空格拼接多行查询，让检索引擎同时匹配多个表述
        return " ".join(lines[:3])

    async def _generate_hyde(self, query: str, config: ChatbotConfig) -> Optional[str]:
        """
        HyDE：生成假想文档用于检索

        返回假想文档文本，用于向量检索
        """
        prompt_template = config.hyde_prompt or self.DEFAULT_HYDE_PROMPT
        prompt = prompt_template.replace("{query}", query)

        result = await self._call_llm_for_retrieval(prompt, config)
        print(f"HyDE 生成结果: {result}")
        if not result or len(result) < 20:
            return None

        return result

    async def _retrieve_knowledge(
        self,
        kb_configs: List[KnowledgeBaseConfig],
        query: str,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        从知识库检索相关信息

        Returns:
            (context_text, citations): 上下文文本 和 引用列表
        """
        all_context = []
        all_citations = []
        knowledge_service = get_knowledge_service(self.db)

        # 判断是否有任何知识库启用了引用
        any_show_citation = any(
            kb.show_citation for kb in kb_configs if kb.enabled
        )

        logger.info(f"开始知识库检索, 配置数量: {len(kb_configs)}, 查询: {query[:50]}...")

        for kb_config in kb_configs:
            if not kb_config.enabled:
                logger.info(f"知识库 {kb_config.knowledge_base_id} 已禁用，跳过")
                continue

            try:
                logger.info(f"检索知识库 {kb_config.knowledge_base_id} ({kb_config.name}), top_k={kb_config.top_k}, threshold={kb_config.score_threshold}")
                results = await knowledge_service.search(
                    kb_id=kb_config.knowledge_base_id,
                    query=query,
                    top_k=kb_config.top_k,
                    score_threshold=kb_config.score_threshold,
                )

                logger.info(f"知识库 {kb_config.knowledge_base_id} 检索到 {len(results)} 条结果")
                for result in results:
                    all_context.append(
                        f"[来源: {result.get('document_name', '未知')}]\n"
                        f"{result['content']}"
                    )

                    # 收集引用信息
                    if kb_config.show_citation:
                        citation = {
                            "knowledge_base_id": kb_config.knowledge_base_id,
                            "knowledge_base_name": kb_config.name,
                            "document_id": result.get("document_id"),
                            "document_name": result.get("document_name", "未知"),
                            "segment_id": result.get("segment_id"),
                            "content": result["content"][:200],
                            "score": round(result.get("score", 0), 4),
                        }
                        # 附加元数据（如页码、标题路径）
                        metadata = result.get("metadata") or {}
                        if metadata.get("page_number"):
                            citation["page_number"] = metadata["page_number"]
                        if metadata.get("header_path"):
                            citation["header_path"] = metadata["header_path"]
                        all_citations.append(citation)
            except Exception as e:
                logger.warning(
                    f"知识库 {kb_config.knowledge_base_id} 检索失败: {e}",
                    exc_info=True
                )

        logger.info(f"知识库检索完成, 共 {len(all_context)} 条上下文, 引用: {len(all_citations)} 条")
        context_text = "\n\n---\n\n".join(all_context) if all_context else ""
        return context_text, all_citations

    def _build_messages(
        self,
        config: ChatbotConfig,
        query: str,
        context_text: str,
        conversation_id: int,
    ) -> List[Dict[str, str]]:
        """构建 LLM 消息列表"""
        messages = []

        # 系统提示词
        system_prompt = config.prompt.system_prompt or "你是一个有用的AI助手。"
        if context_text:
            logger.info(f"添加知识库上下文到系统提示词, 长度: {len(context_text)}")
            system_prompt += f"\n\n参考以下知识库内容回答问题：\n\n{context_text}"
        else:
            logger.info("无知识库上下文")
        messages.append({"role": "system", "content": system_prompt})

        # 历史消息（如果有记忆窗口）
        if config.memory_enabled:
            history = self._get_history(conversation_id, config.memory_window)
            messages.extend(history)

        # 当前用户消息
        messages.append({"role": "user", "content": query})

        return messages

    def _create_conversation(self, app_id: int, user_id: int, first_message: str) -> int:
        """创建新会话"""
        from app.models.conversation import Conversation

        # 使用消息前 20 个字符作为会话标题
        title = first_message[:20] + ("..." if len(first_message) > 20 else "")

        conversation = Conversation(
            app_id=app_id,
            user_id=user_id,
            title=title,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation.id

    def _get_history(
        self, conversation_id: int, window: int
    ) -> List[Dict[str, str]]:
        """获取历史消息"""
        from app.models.conversation import Message

        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(window * 2)  # 用户+助手各一条
            .all()
        )
        messages.reverse()

        return [{"role": m.role, "content": m.content} for m in messages]

    def _save_message(
        self, conversation_id: int, role: str, content: str
    ) -> int:
        """保存消息"""
        from app.models.conversation import Message, Conversation

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.db.add(message)

        # 更新会话时间
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        if conversation:
            conversation.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(message)
        return message.id

    def _generate_demo_response(self, query: str, context_text: str) -> str:
        """生成演示回复（当没有配置 LLM 时使用）"""
        if context_text:
            return f"（演示模式）根据知识库内容，关于「{query[:50]}」的信息如下：\n\n{context_text[:200]}...\n\n如需获得更准确的回答，请配置模型供应商。"
        return f"（演示模式）您问的是：「{query}」\n\n当前未配置 LLM 模型，请在「模型管理」中配置模型供应商后即可正常使用。"

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def list_conversations(
        self, app_id: int, user_id: int, page: int = 1, page_size: int = 20
    ) -> List[ConversationResponse]:
        """获取会话列表"""
        from app.models.conversation import Conversation

        conversations = (
            self.db.query(Conversation)
            .filter(Conversation.app_id == app_id, Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return [ConversationResponse.model_validate(c) for c in conversations]

    def get_conversation_messages(
        self, conversation_id: int, limit: int = 50
    ) -> List[MessageResponse]:
        """获取会话消息列表"""
        from app.models.conversation import Message

        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .all()
        )

        return [MessageResponse.model_validate(m) for m in messages]

    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """删除会话"""
        from app.models.conversation import Conversation, Message

        conversation = (
            self.db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .first()
        )
        if not conversation:
            return False

        # 删除消息
        self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).delete()

        # 删除会话
        self.db.delete(conversation)
        self.db.commit()
        return True


def get_chatbot_service(db: Session) -> ChatbotService:
    return ChatbotService(db)
