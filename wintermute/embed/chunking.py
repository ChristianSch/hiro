from __future__ import annotations


def chunk_content(
    tokenizer,
    content: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    # The complete token sequence is needed before splitting. Disable the
    # tokenizer's model-length warning because only bounded chunks are encoded
    # by the model.
    token_ids = tokenizer.encode(
        content,
        add_special_tokens=False,
        verbose=False,
    )
    step = max_tokens - overlap_tokens
    chunks: list[str] = []
    for start in range(0, len(token_ids), step):
        chunk_ids = token_ids[start:start + max_tokens]
        if not chunk_ids:
            break
        chunk = tokenizer.decode(
            chunk_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        ).strip()
        if chunk:
            chunks.append(chunk)
        if start + max_tokens >= len(token_ids):
            break
    return chunks or [content]
