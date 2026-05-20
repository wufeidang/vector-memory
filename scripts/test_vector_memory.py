"""Vector-Memory \u5355\u5143\u6d4b\u8bd5

\u8fd0\u884c: pytest test_vector_memory.py -v
\u8981\u6c42: pip install pytest
"""
import os
import sys
import time
import json
import pytest

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture(scope="module")
def vm():
    import vector_memory
    return vector_memory


@pytest.fixture
def test_collection(vm):
    name = "test_" + str(int(time.time() * 1000))
    result = vm.create_collection({"name": name})
    assert result.get("success"), f"\u521b\u5efa\u96c6\u5408\u5931\u8d25: {result}"
    vm.switch_collection({"name": name})
    yield name
    vm.switch_collection({"name": "memories"})


class TestCore:
    def test_version(self, vm):
        assert hasattr(vm, "__version__")
        assert vm.__version__ == "2.1.0"

    def test_locks_present(self):
        import core
        for lock_name in ['_client_lock', '_model_lock', '_collection_lock',
                          '_vectorizer_lock', '_reranker_lock']:
            assert hasattr(core, lock_name)


class TestCollections:
    def test_list_collections(self, vm):
        result = vm.list_collections()
        assert result.get("success")
        assert "memories" in result.get("collections", [])

    def test_create_and_delete_collection(self, vm, test_collection):
        result = vm.list_collections()
        assert test_collection in result.get("collections", [])
        result = vm.delete_collection({"name": test_collection})
        assert result.get("success")
        result = vm.list_collections()
        assert test_collection not in result.get("collections", [])

    def test_create_duplicate(self, vm):
        result = vm.create_collection({"name": "memories"})
        assert not result.get("success")


class TestMemories:
    def test_add_memory(self, vm, test_collection):
        result = vm.add_memory({"text": "pytest \u5355\u5143\u6d4b\u8bd5", "collection": test_collection})
        assert result.get("success")

    def test_add_empty_text(self, vm):
        result = vm.add_memory({"text": ""})
        assert not result.get("success")

    def test_add_batch(self, vm, test_collection):
        texts = [f"\u6279\u91cf\u6d4b\u8bd5 {i}" for i in range(3)]
        result = vm.add_batch({"texts": texts, "collection": test_collection})
        assert result.get("success")
        assert result.get("count", 0) == 3

    def test_list_memories(self, vm, test_collection):
        vm.add_memory({"text": "\u5217\u8868\u6d4b\u8bd5", "collection": test_collection})
        result = vm.list_memories({"limit": 10, "collection": test_collection})
        assert result.get("success")
        assert result.get("count", 0) > 0

    def test_clear_memories(self, vm, test_collection):
        vm.add_memory({"text": "\u6e05\u7a7a\u6d4b\u8bd5", "collection": test_collection})
        result = vm.clear_memories({"collection": test_collection})
        assert result.get("success")
        result = vm.list_memories({"collection": test_collection})
        assert result.get("count", 0) == 0


class TestSearch:
    def test_search_with_results(self, vm, test_collection):
        vm.add_memory({"text": "pytest \u6d4b\u8bd5\u6846\u67b6\u8bb0\u5fc6", "collection": test_collection})
        result = vm.search_memories({"text": "pytest", "top_k": 5, "collection": test_collection})
        assert result.get("success")
        assert result.get("count", 0) > 0

    def test_search_empty_query(self, vm):
        result = vm.search_memories({"text": "", "top_k": 5})
        assert not result.get("success")

    def test_search_has_relevance_score(self, vm, test_collection):
        vm.add_memory({"text": "Pytest \u6d4b\u8bd5\u9a71\u52a8\u5f00\u53d1", "collection": test_collection})
        result = vm.search_memories({"text": "\u6d4b\u8bd5", "top_k": 3, "collection": test_collection})
        if result.get("success") and result.get("count", 0) > 0:
            for r in result.get("results", []):
                assert "relevance_score" in r


class TestManagement:
    def test_get_stats(self, vm):
        result = vm.get_stats()
        assert result.get("success")
        assert "count" in result

    def test_export(self, vm):
        result = vm.export_memories({"format": "json"})
        assert result.get("success")
        assert "path" in result

    def test_backup_and_list(self, vm):
        result = vm.backup_memories()
        assert result.get("success")
        result = vm.list_backups()
        assert result.get("success")
        assert result.get("count", 0) > 0


class TestRelations:
    def test_link_and_get_chain(self, vm, test_collection):
        r1 = vm.add_memory({"text": "\u6e90\u5934", "collection": test_collection})
        r2 = vm.add_memory({"text": "\u76ee\u6807", "collection": test_collection})
        id1 = r1.get("ids", [r1.get("id", "")])[0]
        id2 = r2.get("ids", [r2.get("id", "")])[0]
        result = vm.link_memory({"from_id": id1, "to_id": id2})
        assert result.get("success")
        result = vm.get_knowledge_chain({"doc_id": id1, "depth": 1})
        assert result.get("success")

    def test_unlink(self, vm, test_collection):
        r1 = vm.add_memory({"text": "A", "collection": test_collection})
        r2 = vm.add_memory({"text": "B", "collection": test_collection})
        id1 = r1.get("ids", [r1.get("id", "")])[0]
        id2 = r2.get("ids", [r2.get("id", "")])[0]
        vm.link_memory({"from_id": id1, "to_id": id2})
        result = vm.unlink_memory({"from_id": id1, "to_id": id2})
        assert result.get("success")


class TestIncrementalTFIDF:
    def test_rebuild_function_exists(self):
        from search import _rebuild_tfidf_if_needed, _tfidf_cache
        assert callable(_rebuild_tfidf_if_needed)
        assert isinstance(_tfidf_cache, dict)
        assert "doc_count" in _tfidf_cache


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
