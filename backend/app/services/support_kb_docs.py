"""
客服知识库文档生成服务

读取后台客服业务示例数据（订单 / 商品 / 物流 / 退换货政策），
自动生成三类知识库文档并入库向量化：
1. 退换货政策说明
2. 如何下单与物流指引（操作文档）
3. 商品使用说明书（每个商品一篇）

设计要点：
1. **幂等**：按文档名（knowledge_base_id + name）upsert，重复点击不产生孤儿文档。
2. **复用 KnowledgeService.process_document** 做分片 + 向量化，与平台知识库入库流程一致。
3. **错误处理**：单篇失败只记 warning 并回写 error_message，不阻断其余文档。
4. **独立知识库**：统一落到名为「客服知识库（自动生成）」的 KB，不污染用户自建库。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.knowledge import Document, KnowledgeBase
from app.models.support_business import (
    ReturnCategory,
    SupportOrder,
    SupportProduct,
    SupportReturnPolicy,
    SupportShipment,
)
from app.services.knowledge import KnowledgeService
from app.utils.logger import logger

KB_NAME = "客服知识库（自动生成）"
KB_DESCRIPTION = "由客服业务示例数据自动生成（退换货政策 / 下单指引 / 商品说明书），供智能客服助手检索作答。"

# 文档名常量（幂等 upsert 的键）
DOC_RETURN_POLICY = "退换货政策说明"
DOC_ORDER_GUIDE = "如何下单与物流指引"


def _md_section(title: str, body: str) -> str:
    return f"## {title}\n\n{body}\n"


class SupportKbDocService:
    """客服知识库文档生成服务"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 对外入口
    # ------------------------------------------------------------------

    async def generate(self, owner_id: int) -> Dict[str, Any]:
        """生成全部知识库文档并向量化，返回汇总"""
        kb = self._get_or_create_kb(owner_id)
        results: List[Dict[str, object]] = []

        # 1. 退换货政策
        results.append(await self._upsert_and_process(kb, DOC_RETURN_POLICY, self._build_return_policy_md()))
        # 2. 下单与物流指引
        results.append(await self._upsert_and_process(kb, DOC_ORDER_GUIDE, self._build_order_guide_md()))
        # 3. 商品使用说明书（每商品一篇）
        products = self.db.query(SupportProduct).order_by(SupportProduct.id).all()
        for product in products:
            name = f"商品使用说明-{product.name}"
            results.append(await self._upsert_and_process(kb, name, self._build_product_manual_md(product)))

        ok_count = sum(1 for r in results if r.get("status") == "completed")
        return {
            "ok": True,
            "knowledge_base_id": kb.id,
            "knowledge_base_name": kb.name,
            "documents": results,
            "message": f"已生成 {len(results)} 篇文档，其中 {ok_count} 篇向量化成功。",
        }

    # ------------------------------------------------------------------
    # 文档构建
    # ------------------------------------------------------------------

    def _build_return_policy_md(self) -> str:
        policies = (
            self.db.query(SupportReturnPolicy).order_by(SupportReturnPolicy.id).all()
        )
        lines = ["# 退换货政策说明", "", "本文档汇总各品类（电子产品 / 服装 / 图书）的退换货政策，供客服作答参考。", ""]
        if not policies:
            lines.append("> 暂无退换货政策数据。")
        for p in policies:
            lines.append(_md_section(p.category_label or p.category, p.policy_content.strip()))
        return "\n".join(lines)

    def _build_order_guide_md(self) -> str:
        orders = self.db.query(SupportOrder).order_by(SupportOrder.id).all()
        shipments = self.db.query(SupportShipment).order_by(SupportShipment.id).all()

        lines = [
            "# 如何下单与物流指引",
            "",
            "## 如何下单",
            "1. 在商品详情页点击「立即购买」或「加入购物车」；",
            "2. 填写收货信息并选择支付方式，提交订单；",
            "3. 支付成功后系统生成订单号，可在「我的订单」中查看状态；",
            "4. 如需修改收货信息或取消订单，请尽快联系客服。",
            "",
            "## 物流查询",
            "支付后商品将在 1~2 个工作日内发货，发货后可在订单详情查看物流单号与实时位置。",
            "",
        ]

        if orders:
            lines.append("## 示例订单")
            for o in orders:
                lines.append(
                    f"- 订单号 **{o.order_no}**：{o.product}，金额 ¥{o.amount:.2f}，"
                    f"状态 {o.status}"
                    + (f"，下单时间 {o.ordered_at}" if o.ordered_at else "")
                )
            lines.append("")

        if shipments:
            lines.append("## 物流示例")
            for s in shipments:
                lines.append(
                    f"- 订单 **{s.order_no}**：承运 {s.carrier or '—'}，"
                    f"单号 {s.tracking_no or '—'}，当前位于 {s.current_location or '—'}，"
                    f"预计 {s.estimated_text or '以物流为准'}"
                )
            lines.append("")

        return "\n".join(lines)

    def _build_product_manual_md(self, product: SupportProduct) -> str:
        lines = [f"# 商品使用说明：{product.name}", ""]
        if product.price is not None:
            lines.append(f"- 价格：¥{product.price:.2f}")
        if product.warranty:
            lines.append(f"- 质保：{product.warranty}")
        if product.category:
            lines.append(f"- 品类：{product.category}")
        lines.append("")
        if product.description:
            lines.append(_md_section("产品介绍", product.description.strip()))
        features = product.features or []
        if features:
            lines.append(_md_section("核心特性", "\n".join(f"- {f}" for f in features)))
        lines.append(
            _md_section(
                "使用与售后建议",
                "购买后请保留订单号与保修凭证；遇质量问题可在质保期内申请售后，"
                "退换货规则详见《退换货政策说明》。",
            )
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 落库 + 向量化
    # ------------------------------------------------------------------

    async def _upsert_and_process(
        self, kb: KnowledgeBase, name: str, content: str
    ) -> Dict[str, object]:
        """按名幂等 upsert 文档，并触发分片向量化"""
        doc = (
            self.db.query(Document)
            .filter(Document.knowledge_base_id == kb.id, Document.name == name)
            .first()
        )
        if doc is None:
            doc = Document(
                knowledge_base_id=kb.id,
                name=name,
                file_type="markdown",
                status="pending",
            )
            self.db.add(doc)
        doc.content = content
        doc.file_type = "markdown"
        doc.status = "pending"
        doc.error_message = None
        self.db.commit()
        self.db.refresh(doc)

        try:
            ok = await KnowledgeService(self.db).process_document(doc.id)
            self.db.refresh(doc)
            return {
                "document_id": doc.id,
                "name": name,
                "status": doc.status,
                "chunk_count": doc.chunk_count or 0,
                "ok": bool(ok),
            }
        except Exception as exc:  # noqa: BLE001 - 单篇失败不影响其他文档
            logger.error(f"客服知识库文档处理失败 {name}: {exc}")
            self.db.rollback()
            doc = (
                self.db.query(Document)
                .filter(Document.id == doc.id)
                .first()
            )
            if doc:
                doc.status = "failed"
                doc.error_message = str(exc)[:500]
                self.db.commit()
            return {"document_id": doc.id if doc else None, "name": name, "status": "failed", "ok": False}

    def _get_or_create_kb(self, owner_id: int) -> KnowledgeBase:
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.name == KB_NAME).first()
        if kb is None:
            kb = KnowledgeBase(
                name=KB_NAME,
                description=KB_DESCRIPTION,
                owner_id=owner_id,
                kb_type="local",
                status="active",
            )
            self.db.add(kb)
            self.db.commit()
            self.db.refresh(kb)
        return kb


def get_support_kb_doc_service(db: Session) -> SupportKbDocService:
    """客服知识库文档服务工厂"""
    return SupportKbDocService(db)
