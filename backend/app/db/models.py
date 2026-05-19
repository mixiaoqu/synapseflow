"""Database ORM models."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.core.config import config_registry
from app.db.session import Base
from app.utils.time import utc_now

EMBEDDING_DIM = config_registry.get_embedding_config().dim


class User(Base):
    """Application user."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="end_user", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Team(Base):
    """Enterprise team."""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class TeamMember(Base):
    """Membership between users and teams."""

    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), nullable=False, default="member")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SensitiveWordSetting(Base):
    """Scoped sensitive-word runtime settings."""

    __tablename__ = "sensitive_word_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    block_query = Column(Boolean, nullable=False, default=True)
    block_document_publish = Column(Boolean, nullable=False, default=False)
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SensitiveWord(Base):
    """One sensitive word row under the global or team scope."""

    __tablename__ = "sensitive_words"
    __table_args__ = (
        UniqueConstraint("team_id", "normalized_word", name="uq_sensitive_words_team_normalized"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    word = Column(String(255), nullable=False)
    normalized_word = Column(String(255), nullable=False, index=True)
    category = Column(String(50), nullable=True, index=True)
    match_mode = Column(String(20), nullable=False, default="contains")
    enabled = Column(Boolean, nullable=False, default=True)
    remark = Column(Text, nullable=True)
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class KnowledgeBase(Base):
    """Knowledge base under a team."""

    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class KnowledgeBaseMember(Base):
    """Optional per-knowledge-base membership overrides."""

    __tablename__ = "knowledge_base_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), nullable=False, default="viewer")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AssistantProfile(Base):
    """Configurable assistant profile bound to one team/knowledge base scope."""

    __tablename__ = "assistant_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("document_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(100), nullable=False)
    slug = Column(String(120), nullable=False, unique=True, index=True)
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description = Column(Text, nullable=True)
    welcome_message = Column(Text, nullable=True)
    placeholder_text = Column(String(255), nullable=True)
    llm_model_key = Column(String(80), nullable=True, index=True)
    persona_prompt = Column(Text, nullable=True)
    rule_template = Column(Text, nullable=True)
    suggested_prompts = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Product(Base):
    """Business product definition under one team."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(120), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Project(Base):
    """Business project that can expose embedded assistant applications."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("product_id", "code", name="uq_projects_product_code"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(120), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ProjectApp(Base):
    """One embeddable application under a project."""

    __tablename__ = "project_apps"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_project_apps_project_code"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(120), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    default_assistant_id = Column(
        Integer,
        ForeignKey("assistant_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ProjectAppKnowledgeBase(Base):
    """One project application binding to one knowledge base."""

    __tablename__ = "project_app_knowledge_bases"
    __table_args__ = (
        UniqueConstraint(
            "project_app_id",
            "knowledge_base_id",
            name="uq_project_app_kbs_app_kb",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_app_id = Column(
        Integer,
        ForeignKey("project_apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), default=utc_now)


class DocumentCategory(Base):
    """Knowledge-base scoped document category."""

    __tablename__ = "document_categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Document(Base):
    """Document rows belonging to a knowledge base."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    document_type = Column(String(50), nullable=True)
    size = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    parent_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    root_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    is_latest = Column(Boolean, nullable=False, default=True)
    is_current = Column(Boolean, nullable=False, default=True)
    is_live = Column(Boolean, nullable=False, default=False, index=True)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("document_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_path = Column(String(1024), nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    index_status = Column(String(20), nullable=False, default="queued", index=True)
    index_error = Column(Text, nullable=True)
    graph_index_status = Column(String(20), nullable=False, default="queued", index=True)
    graph_index_error = Column(Text, nullable=True)
    graph_indexed_at = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(String(32), nullable=False, default="")
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DocumentChunk(Base):
    """Persisted parent/child chunk relationships for one document."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_kind", "chunk_index", name="uq_document_chunks_doc_kind_index"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_kind = Column(String(20), nullable=False, index=True)
    parent_chunk_id = Column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    prev_chunk_id = Column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    next_chunk_id = Column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    section_path = Column(String(1024), nullable=True)
    block_types = Column(JSON, nullable=True)
    start_offset = Column(Integer, nullable=False, default=0)
    end_offset = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False)
    search_text = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class IndexJob(Base):
    """Persisted indexing job envelope for task-level progress tracking."""

    __tablename__ = "index_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False)
    job_type = Column(String(50), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="queued", index=True)
    total_documents = Column(Integer, nullable=False, default=0)
    queued_documents = Column(Integer, nullable=False, default=0)
    processing_documents = Column(Integer, nullable=False, default=0)
    indexed_documents = Column(Integer, nullable=False, default=0)
    failed_documents = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class IndexJobDocument(Base):
    """One document item inside an indexing job."""

    __tablename__ = "index_job_documents"
    __table_args__ = (
        UniqueConstraint("job_id", "document_id", name="uq_index_job_documents_job_document"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("index_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    expected_content_hash = Column(String(32), nullable=False)
    status = Column(String(20), nullable=False, default="queued", index=True)
    error_message = Column(Text, nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Embedding(Base):
    """Chunk embeddings for vector retrieval."""

    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_chunk_id = Column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text = Column(Text, nullable=False)
    search_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_tsv = Column(TSVECTOR, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)


class ChatSession(Base):
    """Persisted KB chat session metadata."""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", name="uq_chat_sessions_user_session_id"),
        UniqueConstraint(
            "project_app_id",
            "external_user_id",
            "session_id",
            name="uq_chat_sessions_project_app_external_session",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    project_app_id = Column(
        Integer,
        ForeignKey("project_apps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_user_id = Column(String(255), nullable=True, index=True)
    external_user_name = Column(String(255), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistant_id = Column(
        Integer,
        ForeignKey("assistant_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("document_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ChatMessage(Base):
    """One persisted chat turn message inside a KB chat session."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chat_session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class KbChatLog(Base):
    """Persisted KB chat execution log for admin QA and feedback."""

    __tablename__ = "kb_chat_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    project_app_id = Column(
        Integer,
        ForeignKey("project_apps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_user_id = Column(String(255), nullable=True, index=True)
    external_user_name = Column(String(255), nullable=True)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistant_id = Column(
        Integer,
        ForeignKey("assistant_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("document_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    answer_status = Column(String(20), nullable=False, default="answered", index=True)
    retrieval_status = Column(String(30), nullable=True, index=True)
    retrieved_count = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True)
    feedback_value = Column(String(20), nullable=True, index=True)
    feedback_note = Column(Text, nullable=True)
    review_label = Column(String(40), nullable=True, index=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
