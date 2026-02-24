"""RAG pipeline: retrieve relevant chunks and generate answer."""
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

TOP_K = 5
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
) -> list[dict]:
    """Vector similarity search using pgvector cosine distance."""
    embedding_str = "[" + ",".join(map(str, question_embedding)) + "]"
    sql = text("""
        SELECT
            dc.id,
            dc.content,
            dc.document_id,
            d.name AS document_name,
            1 - (dc.embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE dc.tenant_id = :tenant_id
          AND dc.embedding IS NOT NULL
          AND d.status = 'done'
        ORDER BY dc.embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)
    result = await db.execute(
        sql,
        {"embedding": embedding_str, "tenant_id": str(tenant_id), "top_k": top_k},
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]


def build_system_prompt(tenant: Tenant, context: str) -> str:
    base = tenant.system_prompt or (
        "You are a helpful AI assistant. Answer questions based ONLY on the provided context. "
        "If the answer is not in the context, say you don't know. "
        "Never make up information."
    )
    return f"{base}\n\n<context>\n{context}\n</context>"


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


async def run_rag_pipeline(
    question: str,
    tenant: Tenant,
    db: AsyncSession,
) -> dict[str, Any]:
    """Full RAG pipeline: embed → retrieve → generate."""
    embedding_key = tenant.embedding_api_key or tenant.llm_api_key
    emb_model = getattr(tenant, "embedding_model", "ollama:nomic-embed-text")
    question_embedding = await embed_single(question, api_key=embedding_key, embedding_model=emb_model)
    chunks = await retrieve_chunks(question_embedding, tenant.id, db)

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
