"""
智能客服业务数据模型（Demo 示例）

客服 Tool Agent 查询的订单 / 物流 / 商品 / 退换货政策。
数据来自 `docs/智能客服.md` 同款示例，首次启动由 `core/seed.py` 初始化，
运营可在机器人配置的「业务数据」Tab 查看与维护，不依赖真实业务系统。

约定：
- 订单号 `order_no` / 产品号 `product_no` 是业务字符串主键（与文档 ORD-001 / P001 对齐），
  Tool Agent 的 `order_id` / `product_id` 参数即对应这两个字段。
- 物流按 `order_no` 关联订单（一个订单一份物流），`track_shipment(order_id)` 用 order_no 查。
- 退换货政策按 `category` 关联（electronics / clothing / books）。
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import UTCDateTime, Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ReturnCategory:
    """退换货政策分类"""

    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"

    ALL = (ELECTRONICS, CLOTHING, BOOKS)

    LABELS = {
        ELECTRONICS: "电子产品",
        CLOTHING: "服装",
        BOOKS: "图书",
    }


class SupportOrder(Base):
    """订单（Demo 数据）"""

    __tablename__ = "support_orders"
    __table_args__ = (UniqueConstraint("order_no", name="uq_support_orders_no"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(64), nullable=False, unique=True)
    customer_name = Column(String(100), nullable=False, default="")
    product = Column(String(255), nullable=False, default="")
    amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="processing")
    ordered_at = Column(UTCDateTime(timezone=True), nullable=True)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportOrder(id={self.id}, no={self.order_no}, status={self.status})>"


class SupportProduct(Base):
    """商品（Demo 数据）"""

    __tablename__ = "support_products"
    __table_args__ = (UniqueConstraint("product_no", name="uq_support_products_no"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_no = Column(String(64), nullable=False, unique=True)
    name = Column(String(255), nullable=False, default="")
    price = Column(Float, nullable=False, default=0.0)
    warranty = Column(String(100), nullable=True)
    category = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    # 卖点特性列表，如 ["降噪", "30 小时续航", "IPX5", "蓝牙 5.3"]
    features = Column(JSON, nullable=True)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportProduct(id={self.id}, no={self.product_no}, name={self.name})>"


class SupportShipment(Base):
    """物流（按订单号关联）"""

    __tablename__ = "support_shipments"
    __table_args__ = (UniqueConstraint("order_no", name="uq_support_shipments_order"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(64), nullable=False, unique=True, index=True)
    carrier = Column(String(64), nullable=True)
    tracking_no = Column(String(128), nullable=True)
    current_location = Column(String(255), nullable=True)
    # 预计送达的展示文案（如「明天」「3 天后」），比绝对时间更贴近客服话术
    estimated_text = Column(String(100), nullable=True)
    status = Column(String(32), nullable=True)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportShipment(id={self.id}, order_no={self.order_no})>"


class SupportReturnPolicy(Base):
    """退换货政策（按分类）"""

    __tablename__ = "support_return_policies"
    __table_args__ = (UniqueConstraint("category", name="uq_support_policies_cat"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(64), nullable=False, unique=True)
    category_label = Column(String(100), nullable=True)
    policy_content = Column(Text, nullable=False)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportReturnPolicy(id={self.id}, category={self.category})>"
