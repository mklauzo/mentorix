"""Document upload and management API."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_tenant_access
from app.db.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.services.document_service import save_upload, get_document, list_documents, delete_document
from app.tasks.process_document import process_document as process_document_task

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=202)
async def upload_document(
    tenant_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    doc = await save_upload(tenant_id, file, db)
    await db.commit()
    await db.refresh(doc)

    # Dispatch Celery task
    process_document_task.delay(str(doc.id), str(tenant_id))

    return DocumentResponse.model_validate(doc)


@router.get("", response_model=DocumentListResponse)
async def list_tenant_documents(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    docs = await list_documents(tenant_id, db)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document_status(
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    doc = await get_document(doc_id, tenant_id, db)
    return DocumentResponse.model_validate(doc)


@router.delete("/{doc_id}", status_code=204)
async def delete_document_endpoint(
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(require_tenant_access),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_document(doc_id, tenant_id, db)
