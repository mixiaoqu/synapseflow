from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    project_name: str
    version: str
    description: str
    api_v1_str: str


@dataclass(frozen=True)
class ModelConfig:
    model: str
    name: str
    api_key: str
    api_base: str
    temperature: float
    request_timeout: int
    streaming: bool
    max_tokens: int | None = None


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str
    dim: int
    device: str
    batch_size: int


@dataclass(frozen=True)
class IndexingBatchConfig:
    max_docs: int
    max_chunks: int
    max_chars: int


@dataclass(frozen=True)
class RagChunkConfig:
    size: int
    overlap: int


@dataclass(frozen=True)
class RagRetrievalConfig:
    k_first: int
    k_iteration: int
    distance_threshold: float
    distance_threshold_iteration: float
    fallback_top_n: int
    final_top_k: int
    llm_reference_top_k: int | None
    hybrid_enabled: bool
    lexical_k: int
    rrf_k: int
    hybrid_pool_limit: int
    kb_context_max_chars: int


@dataclass(frozen=True)
class RagEvaluateWeights:
    relevance: float
    groundedness: float
    completeness: float


@dataclass(frozen=True)
class RagEvaluateConfig:
    context_max_chars: int
    pass_threshold: float
    weights: RagEvaluateWeights


@dataclass(frozen=True)
class RagConfig:
    chunk: RagChunkConfig
    retrieval: RagRetrievalConfig
    evaluate: RagEvaluateConfig


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
