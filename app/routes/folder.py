"""
app/routes/folder.py
──────────────────────────────────────────────────────────────────────────────
Endpoints:

  POST   /api/folders/                     – Tạo thư mục mới
  GET    /api/folders/                     – Danh sách thư mục gốc
  GET    /api/folders/{folder_id}          – Nội dung thư mục
  GET    /api/folders/{folder_id}/tree     – Cây thư mục đệ quy
  PATCH  /api/folders/{folder_id}/rename   – Đổi tên
  PATCH  /api/folders/{folder_id}/move     – Di chuyển thư mục
  DELETE /api/folders/{folder_id}          – Xóa thư mục
──────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user

# IMPORT ĐÚNG PACKAGE app.*
from app.models import User
from app.models_folder import Folder, Document
from app.schemas_folder import (
    FolderCreate,
    FolderRename,
    FolderMoveRequest,
    FolderOut,
    DocumentOut,
)

router = APIRouter(prefix="/api/folders", tags=["Folder"])


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_folder_or_404(folder_id: int, db: AsyncSession) -> Folder:
    result = await db.execute(
        select(Folder).where(Folder.FolderID == folder_id)
    )

    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy thư mục"
        )

    return folder


def _folder_out(folder: Folder) -> FolderOut:
    return FolderOut(
        folder_id=folder.FolderID,
        name=folder.Name,
        parent_id=folder.ParentID,
        path=folder.Path,
        owner_id=folder.OwnerID,
        created_at=folder.CreatedAt,
        updated_at=folder.UpdatedAt,
    )


async def _build_path(
    parent_id: Optional[int],
    name: str,
    db: AsyncSession,
) -> str:

    if parent_id is None:
        return f"/root/{name}"

    parent = await _get_folder_or_404(parent_id, db)

    return f"{parent.Path}/{name}"


async def _is_descendant(
    folder_id: int,
    target_id: int,
    db: AsyncSession,
) -> bool:

    current_id = target_id

    while current_id is not None:

        if current_id == folder_id:
            return True

        result = await db.execute(
            select(Folder.ParentID).where(
                Folder.FolderID == current_id
            )
        )

        current_id = result.scalar_one_or_none()

    return False


async def _update_path_recursive(
    folder: Folder,
    new_path: str,
    db: AsyncSession,
):

    old_path = folder.Path

    # update current folder
    folder.Path = new_path
    folder.UpdatedAt = datetime.utcnow()

    # update children folders
    result = await db.execute(
        select(Folder).where(
            Folder.Path.like(f"{old_path}/%")
        )
    )

    children = result.scalars().all()

    for child in children:
        child.Path = new_path + child.Path[len(old_path):]
        child.UpdatedAt = datetime.utcnow()

    # update documents
    folder_ids = [folder.FolderID] + [c.FolderID for c in children]

    doc_result = await db.execute(
        select(Document).where(
            Document.FolderID.in_(folder_ids)
        )
    )

    documents = doc_result.scalars().all()

    for doc in documents:

        if doc.Path.startswith(old_path):
            doc.Path = new_path + doc.Path[len(old_path):]
            doc.UpdatedAt = datetime.utcnow()


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE FOLDER
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/", status_code=201)
async def create_folder(
    data: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    # check parent exists
    if data.parent_id:
        await _get_folder_or_404(data.parent_id, db)

    # duplicate name
    duplicate = await db.execute(
        select(Folder).where(
            and_(
                Folder.ParentID == data.parent_id,
                Folder.Name == data.name,
            )
        )
    )

    if duplicate.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Đã tồn tại thư mục cùng tên"
        )

    path = await _build_path(
        data.parent_id,
        data.name,
        db
    )

    folder = Folder(
        Name=data.name,
        ParentID=data.parent_id,
        Path=path,
        OwnerID=current_user.UserID,
    )

    db.add(folder)

    await db.commit()
    await db.refresh(folder)

    return {
        "success": True,
        "message": "Tạo thư mục thành công",
        "data": _folder_out(folder),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LIST ROOT FOLDERS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/")
async def list_root_folders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    result = await db.execute(
        select(Folder)
        .where(
            and_(
                Folder.ParentID == None,
                Folder.OwnerID == current_user.UserID,
            )
        )
        .order_by(Folder.Name)
    )

    folders = result.scalars().all()

    return {
        "success": True,
        "data": [_folder_out(f) for f in folders]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GET FOLDER CONTENTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{folder_id}")
async def get_folder_contents(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    folder = await _get_folder_or_404(folder_id, db)

    # security
    if folder.OwnerID != current_user.UserID:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền truy cập"
        )

    # sub folders
    sub_result = await db.execute(
        select(Folder)
        .where(Folder.ParentID == folder_id)
        .order_by(Folder.Name)
    )

    subfolders = sub_result.scalars().all()

    # documents
    doc_result = await db.execute(
        select(Document)
        .where(Document.FolderID == folder_id)
        .order_by(Document.Name)
    )

    documents = doc_result.scalars().all()

    return {
        "success": True,
        "data": {
            "folder": _folder_out(folder),
            "subfolders": [
                _folder_out(f) for f in subfolders
            ],
            "documents": [
                DocumentOut(
                    document_id=d.DocumentID,
                    folder_id=d.FolderID,
                    name=d.Name,
                    path=d.Path,
                    mime_type=d.MimeType,
                    size=d.Size,
                    created_at=d.CreatedAt,
                )
                for d in documents
            ]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TREE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{folder_id}/tree")
async def get_folder_tree(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    async def build_tree(fid: int):

        folder = await _get_folder_or_404(fid, db)

        if folder.OwnerID != current_user.UserID:
            raise HTTPException(
                status_code=403,
                detail="Không có quyền truy cập"
            )

        result = await db.execute(
            select(Folder)
            .where(Folder.ParentID == fid)
            .order_by(Folder.Name)
        )

        children = result.scalars().all()

        return {
            **_folder_out(folder).model_dump(),
            "children": [
                await build_tree(c.FolderID)
                for c in children
            ]
        }

    return {
        "success": True,
        "data": await build_tree(folder_id)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RENAME
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{folder_id}/rename")
async def rename_folder(
    folder_id: int,
    data: FolderRename,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    folder = await _get_folder_or_404(folder_id, db)

    if folder.OwnerID != current_user.UserID:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền đổi tên"
        )

    # duplicate
    duplicate = await db.execute(
        select(Folder).where(
            and_(
                Folder.ParentID == folder.ParentID,
                Folder.Name == data.name,
                Folder.FolderID != folder_id,
            )
        )
    )

    if duplicate.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Tên thư mục đã tồn tại"
        )

    # new path
    new_path = await _build_path(
        folder.ParentID,
        data.name,
        db
    )

    await _update_path_recursive(
        folder,
        new_path,
        db
    )

    folder.Name = data.name

    await db.commit()
    await db.refresh(folder)

    return {
        "success": True,
        "message": "Đổi tên thành công",
        "data": _folder_out(folder),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MOVE FOLDER
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{folder_id}/move")
async def move_folder(
    folder_id: int,
    data: FolderMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    folder = await _get_folder_or_404(folder_id, db)

    if folder.OwnerID != current_user.UserID:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền di chuyển"
        )

    # move into itself
    if data.target_parent_id == folder_id:
        raise HTTPException(
            status_code=400,
            detail="Không thể di chuyển vào chính nó"
        )

    # target exists
    if data.target_parent_id is not None:

        await _get_folder_or_404(
            data.target_parent_id,
            db
        )

        # prevent circular
        is_child = await _is_descendant(
            folder_id,
            data.target_parent_id,
            db
        )

        if is_child:
            raise HTTPException(
                status_code=400,
                detail="Không thể di chuyển vào thư mục con"
            )

    # duplicate name
    duplicate = await db.execute(
        select(Folder).where(
            and_(
                Folder.ParentID == data.target_parent_id,
                Folder.Name == folder.Name,
                Folder.FolderID != folder_id,
            )
        )
    )

    if duplicate.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Thư mục đã tồn tại ở vị trí đích"
        )

    # new path
    new_path = await _build_path(
        data.target_parent_id,
        folder.Name,
        db
    )

    # update paths
    await _update_path_recursive(
        folder,
        new_path,
        db
    )

    # update parent
    folder.ParentID = data.target_parent_id
    folder.UpdatedAt = datetime.utcnow()

    await db.commit()
    await db.refresh(folder)

    return {
        "success": True,
        "message": "Di chuyển thư mục thành công",
        "data": _folder_out(folder),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    folder = await _get_folder_or_404(folder_id, db)

    if folder.OwnerID != current_user.UserID:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền xóa"
        )

    await db.delete(folder)

    await db.commit()

    return {
        "success": True,
        "message": "Xóa thư mục thành công"
    }