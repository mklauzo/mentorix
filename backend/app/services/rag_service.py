"""RAG pipeline: retrieve relevant chunks and generate answer."""
import re
import uuid
from typing import Any

from fastapi import HTTPException
from openai import AsyncOpenAI, APIStatusError, APIConnectionError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.tenant import Tenant
from app.services.embedding_service import embed_single
from app.schemas.chat import SourceChunk

settings = get_settings()

TOP_K = 12
MAX_PER_DOC = 4          # max chunks from a single document
MAX_CONTEXT_TOKENS = 3000
ANSWER_MAX_TOKENS = 800
TEMPERATURE = 0.2

OLLAMA_PREFIX = "ollama:"


def _get_openai_client(api_key: str | None) -> AsyncOpenAI:
    key = api_key or settings.openai_api_key
    if not key:
        raise ValueError(
            "Brak klucza API OpenAI. Ustaw go w ustawieniach profilu."
        )
    return AsyncOpenAI(api_key=key)


def _get_ollama_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=f"{settings.ollama_url}/v1",
        api_key="ollama",
    )


async def retrieve_chunks(
    question_embedding: list[float],
    tenant_id: uuid.UUID,
    db: AsyncSession,
    top_k: int = TOP_K,
    max_per_doc: int = MAX_PER_DOC,
) -> list[dict]:
    """Vector similarity search with per-document diversity.

    Uses a window function to cap chunks per document (max_per_doc), then
    returns the top_k most similar chunks overall. This prevents a single
    document from monopolising the context window.
    """
    embedding_str = "[" + ",".join(map(str, question_embedding)) + "]"
    sql = text("""
        WITH ranked AS (
            SELECT
                dc.id,
                dc.content,
                dc.document_id,
                d.name AS document_name,
                1 - (dc.embedding <=> CAST(:embedding AS vector)) AS similarity,
                ROW_NUMBER() OVER (
                    PARTITION BY dc.document_id
                    ORDER BY dc.embedding <=> CAST(:embedding AS vector)
                ) AS rn
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.tenant_id = :tenant_id
              AND dc.embedding IS NOT NULL
              AND d.status = 'done'
        )
        SELECT id, content, document_id, document_name, similarity
        FROM ranked
        WHERE rn <= :max_per_doc
        ORDER BY similarity DESC
        LIMIT :top_k
    """)
    result = await db.execute(
        sql,
        {
            "embedding": embedding_str,
            "tenant_id": str(tenant_id),
            "top_k": top_k,
            "max_per_doc": max_per_doc,
        },
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]


_KW_STOP = frozenset({
    'czy', 'jest', 'jakie', 'jaki', 'jaka', 'które', 'który', 'która',
    'ile', 'jak', 'gdzie', 'kiedy', 'masz', 'mam', 'nie', 'tak', 'tych',
    'tego', 'tej', 'proszę', 'powiedz', 'podaj', 'what', 'which', 'where',
    'when', 'does', 'have', 'tell', 'about', 'give', 'list', 'show', 'find',
})


def _extract_keywords(question: str) -> list[str]:
    """Extract keyword stems for ILIKE fallback search.

    Uses 5-char prefix stemming to handle Polish morphology:
    'lodówka' → 'lodów', 'lodówki' → 'lodów' → both match '%lodów%'.
    """
    words = re.sub(r'[?!.,;:()\"\']', ' ', question.lower()).split()
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        if len(w) >= 4 and w not in _KW_STOP:
            stem = w[:5] if len(w) > 5 else w
            if stem not in seen:
                seen.add(stem)
                result.append(f'%{stem}%')
    return result[:4]


async def _keyword_supplement(
    patterns: list[str],
    tenant_id: uuid.UUID,
    db: AsyncSession,
    exclude_ids: set,
    limit: int = 4,
) -> list[dict]:
    """Find chunks via keyword matching (Python-side, Unicode-safe).

    PostgreSQL lower() in C-locale doesn't fold Polish chars (Ó→ó, Ę→ę, etc.),
    so we fetch candidate chunks and filter with Python str.lower() which uses
    full Unicode case folding.
    """
    if not patterns:
        return []

    # keywords: strip surrounding % added by _extract_keywords
    keywords = [p.strip('%') for p in patterns]

    # Fetch all chunks for this tenant (bounded to avoid excessive memory use)
    sql = text("""
        SELECT dc.id, dc.content, dc.document_id, d.name AS document_name,
               0.55 AS similarity
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE dc.tenant_id = :tenant_id
          AND dc.embedding IS NOT NULL
          AND d.status = 'done'
        ORDER BY dc.document_id, dc.chunk_index
        LIMIT 500
    """)
    result = await db.execute(sql, {"tenant_id": str(tenant_id)})
    candidates = [dict(row) for row in result.mappings().all()]

    matched: list[dict] = []
    for chunk in candidates:
        if str(chunk["id"]) in exclude_ids:
            continue
        content_lower = chunk["content"].lower()  # Python Unicode-aware lower()
        if any(kw in content_lower for kw in keywords):
            matched.append(chunk)
            if len(matched) >= limit:
                break
    return matched


_RAG_GUARD = (
    "STRICT RULE: Base your answers ONLY on information found in the <context> section below. "
    "When asked for recommendations, comparisons, or opinions — present and summarize "
    "the relevant options, specs, and prices from the context instead of giving a personal opinion. "
    "If a topic is completely absent from the context, say so briefly in the same language the user used. "
    "Do NOT add any information from your general knowledge. "
    "Do NOT use your general knowledge to fill gaps."
)

def build_system_prompt(tenant: Tenant, context: str) -> str:
    base = tenant.system_prompt or "You are a helpful AI assistant."
    return (
        f"{base}\n\n"
        f"{_RAG_GUARD}\n\n"
        f"<context>\n{context}\n</context>\n\n"
        f"Reminder: answer ONLY based on the context above. If the information is not there, say so."
    )


async def _generate_openai(
    question: str,
    system_prompt: str,
    model: str,
    api_key: str | None,
) -> dict:
    client = _get_openai_client(api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=TEMPERATURE,
        max_tokens=ANSWER_MAX_TOKENS,
    )
    usage = response.usage
    return {
        "answer": response.choices[0].message.content or "",
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


async def _generate_ollama(
    question: str,
    system_prompt: str,
    model: str,
) -> dict:
    client = _get_ollama_client()
    # Small local models often ignore system prompts and add training knowledge.
    # Reinforce the constraint inside the user turn AND use temperature=0.
    user_message = (
        f"IMPORTANT: Use ONLY the information from the context in the system prompt. "
        f"Do NOT use your training knowledge. Do NOT invent numbers, models or facts. "
        f"If the answer is not in the context, say so.\n\nQuestion: {question}"
    )
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,  # deterministic — reduces hallucination in small models
        max_tokens=ANSWER_MAX_TOKENS,
    )
    usage = response.usage
    return {
        "answer": response.choices[0].message.content or "",
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }


async def _generate_gemini(
    question: str,
    system_prompt: str,
    model: str,
    api_key: str | None,
) -> dict:
    key = api_key or ""
    if not key:
        raise ValueError("Brak klucza Google API. Ustaw go w ustawieniach profilu.")
    client = AsyncOpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=key,
    )
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=TEMPERATURE,
        max_tokens=ANSWER_MAX_TOKENS,
    )
    usage = response.usage
    return {
        "answer": response.choices[0].message.content or "",
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }


async def _generate_anthropic(
    question: str,
    system_prompt: str,
    model: str,
    api_key: str | None,
) -> dict:
    from anthropic import AsyncAnthropic
    key = api_key or ""
    if not key:
        raise ValueError("Brak klucza Anthropic API. Ustaw go w ustawieniach profilu.")
    client = AsyncAnthropic(api_key=key)
    response = await client.messages.create(
        model=model,
        max_tokens=ANSWER_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
        temperature=TEMPERATURE,
    )
    usage = response.usage
    return {
        "answer": response.content[0].text if response.content else "",
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }


async def generate_answer(
    question: str,
    tenant: Tenant,
    chunks: list[dict],
) -> dict[str, Any]:
    context_parts = [f"[{i+1}] {chunk['content']}" for i, chunk in enumerate(chunks)]
    context = "\n\n---\n\n".join(context_parts)
    system_prompt = build_system_prompt(tenant, context)
    model = tenant.llm_model
    api_key = tenant.llm_api_key

    try:
        if model.startswith(OLLAMA_PREFIX):
            result = await _generate_ollama(question, system_prompt, model[len(OLLAMA_PREFIX):])
        elif model.startswith("claude-"):
            result = await _generate_anthropic(question, system_prompt, model, api_key)
        elif model.startswith("gemini-"):
            result = await _generate_gemini(question, system_prompt, model, api_key)
        else:
            result = await _generate_openai(question, system_prompt, model, api_key)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except APIStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Błąd API ({model}): {e.status_code} – {e.message}",
        )
    except APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail=f"Brak połączenia z '{model}'. Sprawdź czy Ollama działa i model jest pobrany.",
        )
    except Exception as e:
        # Catch Anthropic SDK errors and other unexpected exceptions
        msg = str(e)
        if "authentication" in msg.lower() or "api_key" in msg.lower() or "unauthorized" in msg.lower():
            raise HTTPException(status_code=400, detail=f"Nieprawidłowy klucz API dla modelu '{model}'.")
        raise HTTPException(status_code=500, detail=f"Błąd modelu '{model}': {msg[:200]}")

    sources = [
        SourceChunk(
            chunk_id=chunk["id"],
            document_name=chunk["document_name"],
            content_preview=chunk["content"][:200],
        )
        for chunk in chunks
    ]
    return {**result, "sources": sources, "chunk_ids": [chunk["id"] for chunk in chunks]}


SMALL_KB_THRESHOLD = 20  # if total chunks <= this, skip vector search and use all chunks


async def _count_chunks(tenant_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        text("""
            SELECT COUNT(*) FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.tenant_id = :tenant_id
              AND dc.embedding IS NOT NULL
              AND d.status = 'done'
        """),
        {"tenant_id": str(tenant_id)},
    )
    return result.scalar() or 0


async def _retrieve_all_chunks(tenant_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Return every chunk for this tenant ordered by document + position."""
    result = await db.execute(
        text("""
            SELECT dc.id, dc.content, dc.document_id, d.name AS document_name,
                   1.0 AS similarity
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.tenant_id = :tenant_id
              AND dc.embedding IS NOT NULL
              AND d.status = 'done'
            ORDER BY d.id, dc.chunk_index
        """),
        {"tenant_id": str(tenant_id)},
    )
    return [dict(row) for row in result.mappings().all()]


async def run_rag_pipeline(
    question: str,
    tenant: Tenant,
    db: AsyncSession,
) -> dict[str, Any]:
    """Full RAG pipeline: embed → retrieve → generate."""
    embedding_key = tenant.embedding_api_key or tenant.llm_api_key
    emb_model = getattr(tenant, "embedding_model", "ollama:nomic-embed-text")

    total = await _count_chunks(tenant.id, db)

    if total <= SMALL_KB_THRESHOLD:
        # Small knowledge base: send ALL chunks — avoids embedding mismatch issues
        # entirely. Gemini/GPT/Claude handle thousands of tokens with no problem.
        chunks = await _retrieve_all_chunks(tenant.id, db)
    else:
        # Large KB: vector similarity search + keyword supplement
        question_embedding = await embed_single(question, api_key=embedding_key, embedding_model=emb_model)
        chunks = await retrieve_chunks(question_embedding, tenant.id, db)

        kw_patterns = _extract_keywords(question)
        if kw_patterns:
            existing_ids = {str(c["id"]) for c in chunks}
            kw_chunks = await _keyword_supplement(
                kw_patterns, tenant.id, db, existing_ids, limit=4
            )
            chunks = chunks + kw_chunks

    if not chunks:
        return {
            "answer": "Nie znalazłem odpowiedzi w dostępnych dokumentach.",
            "sources": [],
            "chunk_ids": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    return await generate_answer(question, tenant, chunks)
