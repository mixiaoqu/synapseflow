from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    project_name: str
    version: str
    description: str
    api_v1_str: str


@dataclass(frozen=True)
class GraphConfig:
    enabled: bool
    indexing_enabled: bool
    provider: str
    uri: str
    username: str
    password: str
    database: str
    extraction_max_chars: int
    extraction_batch_max_chunks: int
    extraction_batch_max_chars: int
    extraction_concurrency: int


@dataclass(frozen=True)
class ModelConfig:
    key: str
    model: str
    name: str
    provider: str
    api_key: str
    api_base: str
    temperature: float | None
    request_timeout: int
    streaming: bool
    max_tokens: int | None = None


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    model: str
    dim: int
    device: str
    batch_size: int
    api_url: str
    api_key: str
    dimensions: int | None


@dataclass(frozen=True)
class IndexingBatchConfig:
    max_docs: int
    max_chunks: int
    max_chars: int


@dataclass(frozen=True)
class RagChunkConfig:
    size: int
    overlap: int
    parent_target_min: int = 1200
    parent_target_max: int = 2500
    child_target_min: int = 400
    child_target_max: int = 900
    split_overlap_units: int = 1
    parent_window_max_chars: int = 1800
    parent_window_neighbor_span: int = 1


@dataclass(frozen=True)
class RagRetrievalProfileConfig:
    recall_k: int
    lexical_k: int
    graph_limit: int
    final_top_k: int
    llm_reference_top_k: int | None
    context_budget: int
    rerank_enabled: bool


@dataclass(frozen=True)
class RagRetrievalConfig:
    k_first: int
    distance_threshold: float
    rerank_threshold: float | None
    final_top_k: int
    llm_reference_top_k: int | None
    hybrid_enabled: bool
    lexical_k: int
    rrf_k: int
    hybrid_pool_limit: int
    kb_context_max_chars: int
    profiles: dict[str, RagRetrievalProfileConfig]


@dataclass(frozen=True)
class RagConfig:
    chunk: RagChunkConfig
    retrieval: RagRetrievalConfig


@dataclass(frozen=True)
class RerankConfig:
    enabled: bool
    provider: str
    api_url: str
    model: str
    instruct: str


@dataclass(frozen=True)
class LoggingFileConfig:
    path: str
    rotation: str
    retention: str


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    json: bool
    log_to_file: bool
    diagnose: bool
    file: LoggingFileConfig
