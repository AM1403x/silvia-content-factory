"""
Embedding utilities for the dedup engine.

Uses sentence-transformers (all-MiniLM-L6-v2) for local, fast embeddings.
The model is lazy-loaded: it is NOT loaded into memory until the first call
to get_embedding(), keeping import time near zero.

Functions:
    get_embedding(text) -> numpy array (384-dim, L2-normalized)
    cosine_similarity(a, b) -> float in [-1, 1]
"""

import numpy as np
from typing import Optional

# Lazy-loaded model reference.
_model: Optional[object] = None


def _load_model():
    """Load the sentence-transformer model on first use."""
    global _model
    if _model is not None:
        return _model

    # Import here so the module loads instantly; the heavy library is
    # only pulled in when someone actually requests an embedding.
    from sentence_transformers import SentenceTransformer
    import sys
    import os

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from config import EMBEDDING_MODEL_NAME

    _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def get_embedding(text: str) -> np.ndarray:
    """Compute a 384-dimensional normalized embedding for *text*.

    Args:
        text: Input string (article summary, title, etc.).

    Returns:
        numpy.ndarray of shape (384,), L2-normalized.
    """
    model = _load_model()
    # encode() returns ndarray of shape (384,) for a single string.
    embedding = model.encode(text, normalize_embeddings=True)
    return np.asarray(embedding, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Both vectors are assumed to be L2-normalized (as returned by
    get_embedding), so cosine similarity simplifies to the dot product.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Float in [-1.0, 1.0]. 1.0 = identical direction.
    """
    # Clamp to [-1, 1] to avoid floating-point edge cases.
    return float(np.clip(np.dot(a, b), -1.0, 1.0))
