from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, JSON, Float
from sqlalchemy.orm import relationship

from app.core.database import Base


class KnowledgeBase(Base):
    """
    知识库模型
    """
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    kb_type = Column(
        Enum("local", "external", name="kb_type_enum"),
        default="local"
    )

    # 所有者
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # 外部知识库配置
    api_endpoint = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    api_config = Column(JSON, nullable=True)

    # 状态
    status = Column(
        Enum("active", "inactive", "processing", name="kb_status_enum"),
        default="active"
    )
    document_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    owner = relationship("User", back_populates="knowledge_bases")
    documents = relationship("Document", back_populates="knowledge_base")
    app_knowledge_bases = relationship("AppKnowledgeBase", back_populates="knowledge_base")

    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, name={self.name}, type={self.kb_type})>"


class Document(Base):
    """
    文档模型
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    file_type = Column(
        Enum("pdf", "excel", "markdown", "docx", "html", "txt", "epub", name="file_type_enum"),
        nullable=False
    )
    file_size = Column(Integer, nullable=True)  # 字节
    source_type = Column(String(20), default="file")  # "file" 或 "url"
    url = Column(String(2000), nullable=True)  # 爬取来源 URL

    # 文档处理状态
    status = Column(String(20), default="pending")
    error_message = Column(Text, nullable=True)

    # 分片策略
    chunk_strategy = Column(String(20), default="sliding_window", nullable=True)

    # 文档内容
    content = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    segments = relationship("DocumentSegment", back_populates="document")

    def __repr__(self):
        return f"<Document(id={self.id}, name={self.name}, status={self.status})>"


class DocumentSegment(Base):
    """
    文档分段模型
    """
    __tablename__ = "document_segments"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    position = Column(Integer, nullable=False)  # 在文档中的位置

    # 向量embedding
    embedding = Column(JSON, nullable=True)  # 存储向量

    # 元数据
    metadata_ = Column("metadata", JSON, nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    document = relationship("Document", back_populates="segments")

    def __repr__(self):
        return f"<DocumentSegment(id={self.id}, document_id={self.document_id})>"
