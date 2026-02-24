"""Embedding service: Ollama (default, free) or OpenAI (if sk-... key provided).

Both produce 768-dim vectors:
- Ollama: nomic-embed-text or mxbai-embed-large (768 dims)
- OpenAI: text-embedding-3-small with dimensions=768

embedding_model values:
  "ollama:nomic-embed-text"  – default, free, local
  "ollama:mxbai-embed-large" – higher quality, local
  "openai"                   – text-embedding-3-small via OpenAI API (requires sk-... key)
"""
from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()

EMBEDDING_MODEL_OPENAI = "text-embedding-3-small"
EMBEDDING_DIM = 768
BATCH_SIZE = 100

DEFAULT_EMBEDDING_MODEL = "ollama:nomic-embed-text"


def _is_openai_key(key: str | None) -> bool:
    return bool(key and key.startswith("sk-"))


def _resolve_ollama_model(embedding_model: str) -> str:
    """Strip 'ollama:' prefix to get the actual Ollama model name."""
    return embedding_model.removeprefix("ollama:")


async def embed_texts(
    texts: list[str],
    api_key: str | None = None,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> tuple[list[list[float]], int]:
    """
    Embed texts in batches. Returns (embeddings, total_tokens).

    Routing:
    - embedding_model == "openai" → OpenAI text-embedding-3-small (needs sk-... key)
    - embedding_model starts with "ollama:" → Ollama local model
    - If api_key is sk-... and embedding_model is not set → fall back to OpenAI
    """
    if embedding_model == "openai":
        # Explicit OpenAI selection
        key = api_key or settings.openai_api_key
        if not _is_openai_key(key):
            # No valid key – fall back to Ollama default
            return await _embed_ollama(texts, DEFAULT_EMBEDDING_MODEL.removeprefix("ollama:"))
        return await _embed_openai(texts, key)

    if embedding_model.startswith("ollama:"):
        return await _embed_ollama(texts, _resolve_ollama_model(embedding_model))

    # Legacy fallback: if api_key is sk-... use OpenAI regardless
    if _is_openai_key(api_key):
        return await _embed_openai(texts, api_key)

    return await _embed_ollama(texts, DEFAULT_EMBEDDING_MODEL.removeprefix("ollama:"))


async def _embed_openai(texts: list[str], api_key: str) -> tuple[list[list[float]], int]:
    client = AsyncOpenAI(api_key=api_key)
    all_embeddings: list[list[float]] = []
    total_tokens = 0
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL_OPENAI,
            input=batch,
            dimensions=EMBEDDING_DIM,
        )
        all_embeddings.extend(item.embedding for item in response.data)
        total_tokens += response.usage.total_tokens
    return all_embeddings, total_tokens


async def _embed_ollama(texts: list[str], model: str) -> tuple[list[list[float]], int]:
    client = AsyncOpenAI(
        base_url=f"{settings.ollama_url}/v1",
        api_key="ollama",
    )
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        response = await client.embeddings.create(
            model=model,
            input=batch,
        )
        all_embeddings.extend(item.embedding for item in response.data)
    return all_embeddings, 0  # Ollama doesn't report token usage


async def embed_single(
    text: str,
    api_key: str | None = None,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[float]:
    embeddings, _ = await embed_texts([text], api_key=api_key, embedding_model=embedding_model)
    return embeddings[0]
