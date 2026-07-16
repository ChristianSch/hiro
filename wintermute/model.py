from __future__ import annotations

import logging

from sentence_transformers import SentenceTransformer


def load_embedding_model(
    model_name: str,
    device: str,
    dimensions: int,
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
        return _validate_dimensions(model, model_name, dimensions)
    except OSError as local_error:
        if not allow_download:
            raise RuntimeError(
                f"embedding model {model_name!r} is not available locally and downloads are disabled"
            ) from local_error

    logging.info("Embedding model not found locally; allowing Hugging Face download: %s", model_name)
    model = SentenceTransformer(
        model_name,
        device=device,
        local_files_only=False,
    )
    return _validate_dimensions(model, model_name, dimensions)


def _validate_dimensions(
    model: SentenceTransformer,
    model_name: str,
    expected: int,
) -> SentenceTransformer:
    actual = model.get_sentence_embedding_dimension()
    if actual != expected:
        raise RuntimeError(
            f"embedding model {model_name!r} produces {actual} values; configured dimensions is {expected}"
        )
    return model
