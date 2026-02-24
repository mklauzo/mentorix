"""Text chunker: RecursiveCharacterTextSplitter-style implementation."""
from typing import Generator

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    text = text.strip()
    if not text:
        return []

    chunks = _recursive_split(text, SEPARATORS, chunk_size)

    # Apply overlap by merging adjacent chunks
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    overlapped = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            overlapped.append(chunk)
            continue
        # Prepend tail of previous chunk
        prev_tail = chunks[i - 1][-overlap:]
        merged = prev_tail + " " + chunk
        overlapped.append(merged[:chunk_size + overlap])

    return overlapped


def _recursive_split(text: str, separators: list[str], chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    # Try each separator
    for sep in separators:
        if sep and sep in text:
            parts = text.split(sep)
            chunks = []
            current = ""
            for part in parts:
                candidate = current + sep + part if current else part
                if len(candidate) <= chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = part
            if current:
                chunks.append(current)

            # Recurse on oversized chunks
            result = []
            for c in chunks:
                if len(c) > chunk_size:
                    result.extend(_recursive_split(c, separators[separators.index(sep) + 1:], chunk_size))
                else:
                    result.append(c)
            return result

    # No separator works: hard split
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
