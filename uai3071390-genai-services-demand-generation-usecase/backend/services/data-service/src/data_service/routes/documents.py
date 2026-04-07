"""
Document upload / retrieval routes.

GET  /api/equipment/{esn}/documents
POST /api/equipment/{esn}/documents   (multipart/form-data)
"""

from typing import Any

from fastapi import APIRouter, File, Form, UploadFile

from data_service.mock_services.documents import get_documents_by_equipment, upload_document

router = APIRouter(prefix="/dataservices/api/v1/equipment", tags=["documents"])


@router.get("/{esn}/documents")
async def get_equipment_documents(esn: str) -> dict[str, list[dict[str, Any]]]:
    return {"documents": get_documents_by_equipment(esn)}


@router.post("/{esn}/documents", status_code=201)
async def upload_equipment_document(
    esn: str,
    file: UploadFile = File(...),
    category: str = Form(default="General"),
) -> dict[str, object]:
    content = await file.read()
    document = upload_document(
        {
            "filename": file.filename or "upload",
            "fileType": file.content_type or "application/octet-stream",
            "fileSize": len(content),
            "category": category,
            "uploadedBy": "user_001",
            "uploadedByName": "Demo User",
            "tags": [esn, category],
            "relatedEquipment": esn,
            "description": f"Uploaded {file.filename}",
            "metadata": {},
        }
    )
    return {"document": document}
