"""Application settings. Every tunable lives here, sourced from the environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Required
    gemini_api_key: str
    
    # Store indices separately for Gemini since dimensions (768) differ from OpenAI (1536)
    chroma_persist_dir: str = "./data/chroma_gemini"
    bm25_persist_dir: str = "./data/bm25_gemini"
    
    # Retrieval Settings
    bm25_weight: float = 0.3
    dense_weight: float = 0.7
    hybrid_k: int = 15
    rerank_top_k: int = 5
    
    # Model Configuration
    embedding_model: str = "gemini-embedding-2"
    generation_model: str = "gemini-3.1-flash-lite"
    judge_model: str = "gemini-3.1-flash-lite"
    
    # Data Storage
    collection_name: str = "rag_chunks_gemini"
    documents_dir: str = "./data/documents"
    sample_corpus_dir: str = "./data/sample_corpus"
    golden_qa_path: str = "./data/golden_qa.json"
    query_log_path: str = "./data/query_log.json"
    eval_runs_path: str = "./data/eval_runs.json"

    dedup_threshold: float = 0.95
    rrf_k: int = 60
    default_dense_weight: float = 0.7
    default_top_k: int = 5
    candidate_pool_size: int = 10

    # Confidence weights (must sum to 1.0)
    weight_retrieval: float = 0.3
    weight_citation: float = 0.4
    weight_completeness: float = 0.3

    # Eval: sequential by default so low-TPM OpenAI orgs don't hit 429 storms
    eval_concurrency: int = 1

    # Hard cap on simultaneously indexed documents
    max_documents: int = 8

    # Misc
    log_level: str = "INFO"
    query_log_max_entries: int = 200
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # openai_api_key comes from env


settings = get_settings()
