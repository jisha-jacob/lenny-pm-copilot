"""Shared embedding helper for ingestion (ingest.py) and retrieval.

Both sides must embed with the exact same model/library (see
_docs/plan.md section 6) so query and document vectors live in the same
space.
"""

from fastembed import TextEmbedding

MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

# Keeps peak memory low on constrained hosts (a local dev machine here; the
# Streamlit Community Cloud free tier at query time -- see _docs/plan.md
# section 6). onnxruntime otherwise: (a) may spin up one thread per core,
# each holding its own working buffers, and (b) pre-allocates a growable
# memory arena sized well beyond steady-state need. threads=1 and
# enable_cpu_mem_arena=False trade some throughput for a much smaller,
# more predictable memory footprint.
BATCH_SIZE = 8

_model = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(
            model_name=MODEL_NAME,
            threads=1,
            enable_cpu_mem_arena=False,
        )
    return _model


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed chunk texts for storage.

    nomic-embed-text-v1.5 requires a "search_document: " task prefix for
    good retrieval quality -- fastembed does not add this automatically
    for this model (its passage_embed/query_embed both fall back to a
    plain, unprefixed embed() call), so it's added explicitly here.
    """
    prefixed = [f"search_document: {t}" for t in texts]
    return [vec.tolist() for vec in _get_model().embed(prefixed, batch_size=BATCH_SIZE)]


def embed_query(text: str) -> list[float]:
    """Embed a user question for retrieval (see embed_documents' note on prefixes)."""
    vec = next(iter(_get_model().embed([f"search_query: {text}"], batch_size=BATCH_SIZE)))
    return vec.tolist()
