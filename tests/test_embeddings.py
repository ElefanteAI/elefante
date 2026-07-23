"""Regression coverage for the local embedding-runtime contract."""

import sys
from types import SimpleNamespace

from src.core.embeddings import EmbeddingService


def test_sentence_transformer_loader_uses_current_dimension_api(monkeypatch):
    """SentenceTransformers 5.x removed the legacy dimension accessor."""

    class FakeSentenceTransformer:
        def __init__(self, model_name, device):
            self.model_name = model_name
            self.device = device

        def get_embedding_dimension(self):
            return 768

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    service = EmbeddingService(model="thenlper/gte-base")

    service._load_sentence_transformer()

    assert service.get_embedding_dimension() == 768
    assert service._model.model_name == "thenlper/gte-base"
    assert service._model.device == service.device
