from __future__ import annotations

import logging

from sentence_transformers import SentenceTransformer


def load_embedding_model(
    model_name: str,
    device: str,
    allow_download: bool,
) -> SentenceTransformer:
    """Load from the local Hugging Face cache before allowing network access."""
    try:
        model = SentenceTransformer(
            model_name,
            device=device,
            local_files_only=True,
        )
        logging.info("Loaded embedding model from local files: %s", model_name)
        return model
    except OSError as local_error:
        if not allow_download:
            raise RuntimeError(
                f"embedding model {model_name!r} is not available locally and downloads are disabled"
            ) from local_error

    logging.info("Embedding model not found locally; allowing Hugging Face download: %s", model_name)
    return SentenceTransformer(
        model_name,
        device=device,
        local_files_only=False,
    )
