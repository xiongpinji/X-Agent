from backend.app.services.memory.qdrant_client import vector_client
from backend.app.services.observability.langfuse_client import langfuse_client


def test_real_client_feature_flags_are_available() -> None:
    assert hasattr(vector_client, "get_collection_names")
    assert hasattr(langfuse_client, "has_real_client")
