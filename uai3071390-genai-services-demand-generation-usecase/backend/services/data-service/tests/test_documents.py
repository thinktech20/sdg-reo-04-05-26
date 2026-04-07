"""
Unit tests — GET  /dataservices/api/v1/equipment/{esn}/documents
             POST /dataservices/api/v1/equipment/{esn}/documents  (multipart)

             Direct tests for mock_services/documents.py helper functions.
"""

import io
from fastapi.testclient import TestClient

from data_service.mock_services.documents import (
    MOCK_DOCUMENTS,
    delete_document,
    get_all_documents,
    get_document,
    get_documents_by_assessment,
    get_download_url,
    search_documents,
    upload_document,
)


class TestGetDocuments:
    def test_returns_documents_for_known_esn(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/GT12345/documents")
        assert resp.status_code == 200
        payload = resp.json()
        assert "documents" in payload
        assert len(payload["documents"]) >= 1
        assert payload["documents"][0]["relatedEquipment"] == "GT12345"

    def test_returns_documents_for_all_known_esns(self, client: TestClient):
        for esn in ("GT12345",):
            resp = client.get(f"/dataservices/api/v1/equipment/{esn}/documents")
            assert resp.status_code == 200
            assert len(resp.json()["documents"]) >= 1

        for esn in ("92307", "GT67890"):
            resp = client.get(f"/dataservices/api/v1/equipment/{esn}/documents")
            assert resp.status_code == 200
            assert resp.json()["documents"] == []

    def test_unknown_esn_returns_empty_list_or_404(self, client: TestClient):
        resp = client.get("/dataservices/api/v1/equipment/UNKNOWN_ESN/documents")
        # Route may return 200 empty list or 404 — both are acceptable
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.json()["documents"] == []


class TestUploadDocument:
    def test_upload_document(self, client: TestClient):
        file_content = b"Sample PDF content"
        resp = client.post(
            "/dataservices/api/v1/equipment/GT12345/documents",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
            data={"category": "Field Service Report"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "document" in data

    def test_upload_creates_document_with_metadata(self, client: TestClient):
        file_content = b"Another document"
        resp = client.post(
            "/dataservices/api/v1/equipment/GT12345/documents",
            files={"file": ("report.pdf", io.BytesIO(file_content), "application/pdf")},
            data={"category": "Equipment Report"},
        )
        assert resp.status_code == 201
        doc = resp.json().get("document", {})
        assert doc.get("relatedEquipment") == "GT12345"
        assert doc.get("filename") == "report.pdf"
        assert doc.get("category") == "Equipment Report"

    def test_upload_default_category(self, client: TestClient):
        file_content = b"No category provided"
        resp = client.post(
            "/dataservices/api/v1/equipment/GT12345/documents",
            files={"file": ("doc.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert resp.status_code == 201
        doc = resp.json()["document"]
        assert doc["category"] == "General"

    def test_upload_no_file_422(self, client: TestClient):
        resp = client.post(
            "/dataservices/api/v1/equipment/GT12345/documents",
            data={"category": "Missing File"},
        )
        assert resp.status_code == 422


# ── Direct tests for mock_services/documents.py helper functions ──────────────


class TestGetDocumentById:
    def test_returns_known_document(self):
        doc = get_document("doc_001")
        assert doc is not None
        assert doc["id"] == "doc_001"
        assert doc["relatedEquipment"] == "GT12345"

    def test_returns_none_for_unknown_id(self):
        assert get_document("nonexistent_id") is None


class TestGetDocumentsByAssessment:
    def test_returns_docs_for_known_assessment(self):
        docs = get_documents_by_assessment("asmt_001")
        assert isinstance(docs, list)
        assert all(d["relatedAssessment"] == "asmt_001" for d in docs)

    def test_returns_empty_for_unknown_assessment(self):
        docs = get_documents_by_assessment("nonexistent_assessment")
        assert docs == []


class TestDeleteDocument:
    def test_delete_existing_document(self):
        # Upload first, then delete
        doc = upload_document({"filename": "to_delete.pdf", "category": "Test"})
        doc_id = doc["id"]
        assert doc_id in MOCK_DOCUMENTS
        assert delete_document(doc_id) is True
        assert doc_id not in MOCK_DOCUMENTS

    def test_delete_nonexistent_returns_false(self):
        assert delete_document("does_not_exist") is False


class TestGetAllDocuments:
    def test_returns_list(self):
        docs = get_all_documents()
        assert isinstance(docs, list)
        assert len(docs) >= 3  # at least the sample docs


class TestSearchDocuments:
    def test_search_by_query(self):
        results = search_documents(query="Reliability")
        assert isinstance(results, list)
        assert any("Reliability" in d.get("filename", "") or "Reliability" in d.get("description", "") for d in results)

    def test_search_by_category(self):
        results = search_documents(category="Equipment Report")
        assert all(d["category"] == "Equipment Report" for d in results)

    def test_search_by_tags(self):
        results = search_documents(tags=["FSR"])
        assert isinstance(results, list)
        assert all(any("FSR" in t for t in d.get("tags", [])) for d in results)

    def test_search_no_filters_returns_all(self):
        all_docs = get_all_documents()
        results = search_documents()
        assert len(results) == len(all_docs)

    def test_search_no_match_returns_empty(self):
        results = search_documents(query="zzz_nonexistent_zzz")
        assert results == []


class TestGetDownloadUrl:
    def test_returns_url_for_known_document(self):
        result = get_download_url("doc_001")
        assert result is not None
        assert "url" in result
        assert "expiresAt" in result
        assert "filename" in result

    def test_returns_none_for_unknown_document(self):
        assert get_download_url("nonexistent_id") is None
