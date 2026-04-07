"""
Mock Documents Data
Provides sample document metadata and mock storage
"""

import uuid
from datetime import datetime
from typing import Any

# In-memory documents storage
MOCK_DOCUMENTS: dict[str, dict[str, Any]] = {}

# Sample documents for demo
SAMPLE_DOCUMENTS = {
    "doc_001": {
        "id": "doc_001",
        "filename": "ER-2026-001-Traction-Motor-Report.pdf",
        "originalName": "ER-2026-001-Traction-Motor-Report.pdf",
        "fileType": "application/pdf",
        "fileSize": 2457600,  # 2.4 MB
        "s3Key": "documents/equipment/GT12345/ER-2026-001-Traction-Motor-Report.pdf",
        "uploadedBy": "user_001",
        "uploadedByName": "John Doe",
        "uploadedAt": "2026-02-10T09:15:00Z",
        "category": "Equipment Report",
        "tags": ["ER Case", "Traction Motor", "GT12345", "train-001"],
        "relatedEquipment": "GT12345",
        "relatedUnit": "train-001",
        "relatedAssessment": "asmt_001",
        "description": "Equipment Report documenting traction motor degradation findings",
        "downloadUrl": "https://mock-storage.example.com/documents/doc_001/download",
        "metadata": {
            "caseNumber": "ER-2026-001",
            "reportDate": "2026-02-08",
            "technician": "Mike Johnson",
            "location": "Chicago Maintenance Facility",
        },
    },
    "doc_002": {
        "id": "doc_002",
        "filename": "FSR-2026-010-Quarterly-Inspection.pdf",
        "originalName": "FSR-2026-010-Quarterly-Inspection.pdf",
        "fileType": "application/pdf",
        "fileSize": 1843200,  # 1.8 MB
        "s3Key": "documents/equipment/GT12345/FSR-2026-010-Quarterly-Inspection.pdf",
        "uploadedBy": "user_002",
        "uploadedByName": "Sarah Chen",
        "uploadedAt": "2026-02-12T14:30:00Z",
        "category": "Field Service Report",
        "tags": ["FSR", "Quarterly Inspection", "GT12345"],
        "relatedEquipment": "GT12345",
        "relatedUnit": "train-001",
        "relatedAssessment": "asmt_001",
        "description": "Quarterly preventive maintenance inspection results",
        "downloadUrl": "https://mock-storage.example.com/documents/doc_002/download",
        "metadata": {
            "fsrNumber": "FSR-2026-010",
            "reportDate": "2026-02-11",
            "technician": "Robert Martinez",
            "serviceType": "Preventive Maintenance",
        },
    },
    "doc_003": {
        "id": "doc_003",
        "filename": "Reliability-Assessment-GT12345.pdf",
        "originalName": "Reliability-Assessment-GT12345.pdf",
        "fileType": "application/pdf",
        "fileSize": 3145728,  # 3 MB
        "s3Key": "documents/assessments/asmt_001/Reliability-Assessment-GT12345.pdf",
        "uploadedBy": "system",
        "uploadedByName": "System Generated",
        "uploadedAt": "2026-02-18T14:45:00Z",
        "category": "Assessment Report",
        "tags": ["Reliability", "Risk Assessment", "Generated"],
        "relatedEquipment": "GT12345",
        "relatedUnit": "train-001",
        "relatedAssessment": "asmt_001",
        "description": "AI-generated reliability risk assessment report",
        "downloadUrl": "https://mock-storage.example.com/documents/doc_003/download",
        "metadata": {
            "assessmentId": "asmt_001",
            "generatedDate": "2026-02-18",
            "riskLevel": "Medium",
            "overallScore": 72,
        },
    },
}

# Initialize with sample data
MOCK_DOCUMENTS.update(SAMPLE_DOCUMENTS)


def get_document(document_id: str) -> dict[str, Any] | None:
    """Get document metadata by ID"""
    return MOCK_DOCUMENTS.get(document_id)


def get_documents_by_equipment(esn: str) -> list[dict[str, Any]]:
    """Get all documents related to specific equipment"""
    return [
        doc for doc in MOCK_DOCUMENTS.values()
        if doc.get("relatedEquipment") == esn
    ]


def get_documents_by_assessment(assessment_id: str) -> list[dict[str, Any]]:
    """Get all documents related to specific assessment"""
    return [
        doc for doc in MOCK_DOCUMENTS.values()
        if doc.get("relatedAssessment") == assessment_id
    ]


def upload_document(file_data: dict[str, Any]) -> dict[str, Any]:
    """
    Mock document upload

    Args:
        file_data: dict with keys: filename, fileType, fileSize, category,
                   uploadedBy, uploadedByName, tags, relatedEquipment,
                   relatedUnit, relatedAssessment, description

    Returns:
        Document metadata dict
    """
    document_id = f"doc_{uuid.uuid4().hex[:8]}"

    # Generate mock S3 key
    category_path = file_data.get("category", "general").lower().replace(" ", "-")
    s3_key = f"documents/{category_path}/{file_data.get('filename')}"

    document = {
        "id": document_id,
        "filename": file_data.get("filename"),
        "originalName": file_data.get("filename"),
        "fileType": file_data.get("fileType", "application/octet-stream"),
        "fileSize": file_data.get("fileSize", 0),
        "s3Key": s3_key,
        "uploadedBy": file_data.get("uploadedBy", "unknown"),
        "uploadedByName": file_data.get("uploadedByName", "Unknown User"),
        "uploadedAt": datetime.now().isoformat() + "Z",
        "category": file_data.get("category", "General"),
        "tags": file_data.get("tags", []),
        "relatedEquipment": file_data.get("relatedEquipment"),
        "relatedUnit": file_data.get("relatedUnit"),
        "relatedAssessment": file_data.get("relatedAssessment"),
        "description": file_data.get("description", ""),
        "downloadUrl": f"https://mock-storage.example.com/documents/{document_id}/download",
        "metadata": file_data.get("metadata", {}),
    }

    MOCK_DOCUMENTS[document_id] = document
    return document


def delete_document(document_id: str) -> bool:
    """Delete a document"""
    if document_id in MOCK_DOCUMENTS:
        del MOCK_DOCUMENTS[document_id]
        return True
    return False


def get_all_documents() -> list[dict[str, Any]]:
    """Get all documents"""
    return list(MOCK_DOCUMENTS.values())


def search_documents(
    query: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Search documents by query, category, or tags

    Args:
        query: Text search query (searches filename and description)
        category: Filter by category
        tags: List of tags to filter by

    Returns:
        List of matching documents
    """
    results = list(MOCK_DOCUMENTS.values())

    if query:
        query_lower = query.lower()
        results = [
            doc
            for doc in results
            if query_lower in doc.get("filename", "").lower() or query_lower in doc.get("description", "").lower()
        ]

    if category:
        results = [
            doc for doc in results
            if doc.get("category") == category
        ]

    if tags:
        results = [
            doc for doc in results
            if any(tag in doc.get("tags", []) for tag in tags)
        ]

    return results


def get_download_url(document_id: str) -> dict[str, Any] | None:
    """Get pre-signed download URL for document"""
    doc = MOCK_DOCUMENTS.get(document_id)
    if doc:
        # In real implementation, generate presigned S3 URL
        # For mock, return the static URL with expiry timestamp
        expires = datetime.now().timestamp() + 3600  # 1 hour expiry
        return {
            "url": doc["downloadUrl"],
            "expiresAt": datetime.fromtimestamp(expires).isoformat() + "Z",
            "filename": doc["filename"],
        }
    return None
