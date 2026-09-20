import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_membership, require_role
from app.core.errors import api_error
from app.database import get_session
from app.models import Document, Membership
from app.schemas.document import DocumentRead, DocumentStatus, DocumentStatusRead
from app.schemas.membership import MembershipRole
from app.services import storage
from app.services.rag import vector_store
from app.services.rag.parsers import resolve_mime
from app.tasks.ingest import ingest_document

router = APIRouter()


@router.post(
    "/{tenant_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    tenant_id: int,
    file: UploadFile = File(...),
    membership: Membership = Depends(require_role(MembershipRole.OWNER, MembershipRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Document:
    settings = get_settings()

    mime = resolve_mime(file.filename or "", file.content_type)
    if mime is None:
        raise api_error(
            422,
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, DOCX, TXT and MD files are supported",
        )

    content = await file.read()
    if len(content) == 0:
        raise api_error(
            422,
            "EMPTY_FILE",
            "The uploaded file is empty",
        )
    if len(content) > settings.max_upload_bytes:
        raise api_error(
            413,
            "FILE_TOO_LARGE",
            f"The file exceeds the maximum size of {settings.max_upload_mb} MB",
        )

    stored_name = f"{uuid.uuid4().hex}{Path(file.filename or '').suffix.lower()}"
    storage_path = storage.save_upload(tenant_id, stored_name, content)

    document = Document(
        tenant_id=tenant_id,
        uploader_id=membership.user_id,
        filename=file.filename or stored_name,
        mime=mime,
        size=len(content),
        status=DocumentStatus.PENDING,
        storage_path=storage_path,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    await ingest_document.kiq(document.id)
    return document


@router.get("/{tenant_id}/documents", response_model=List[DocumentRead])
async def list_documents(
    tenant_id: int,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> List[Document]:
    statement = (
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .order_by(Document.id.desc())
    )
    return (await session.exec(statement)).all()


@router.get("/{tenant_id}/documents/{document_id}", response_model=DocumentStatusRead)
async def get_document_status(
    tenant_id: int,
    document_id: int,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> Document:
    document = await session.get(Document, document_id)
    if document is None or document.tenant_id != tenant_id:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "DOCUMENT_NOT_FOUND",
            "Document not found",
        )
    return document


@router.get("/{tenant_id}/documents/{document_id}/file")
async def download_document(
    tenant_id: int,
    document_id: int,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    document = await session.get(Document, document_id)
    if document is None or document.tenant_id != tenant_id:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "DOCUMENT_NOT_FOUND",
            "Document not found",
        )

    path = Path(document.storage_path)
    if not path.is_file():
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "DOCUMENT_FILE_NOT_FOUND",
            "Stored document file not found",
        )

    return FileResponse(
        path,
        media_type=document.mime,
        filename=document.filename,
        content_disposition_type="inline",
    )


@router.delete(
    "/{tenant_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    tenant_id: int,
    document_id: int,
    membership: Membership = Depends(require_role(MembershipRole.OWNER, MembershipRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    document = await session.get(Document, document_id)
    if document is None or document.tenant_id != tenant_id:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "DOCUMENT_NOT_FOUND",
            "Document not found",
        )

    storage.delete_file(document.storage_path)

    client = vector_store.get_qdrant_client()
    try:
        await vector_store.delete_document_chunks(client, tenant_id, document_id)
    finally:
        await client.close()

    await session.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
