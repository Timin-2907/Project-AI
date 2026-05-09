"""
app/routes/folder.py
──────────────────────────────────────────────────────────────────────────────
Endpoints:

  POST   /api/folders/                      – Tạo thư mục mới
  GET    /api/folders/                      – Danh sách thư mục gốc
  GET    /api/folders/{folder_id}          – Nội dung thư mục (con + tài liệu)
  GET    /api/folders/{folder_id}/tree     – Cây thư mục đệ quy
  PATCH  /api/folders/{folder_id}/rename   – Đổi tên
  PATCH  /api/folders/{folder_id}/move     – ⭐ Di chuyển thư mục
  DELETE /api/folders/{folder_id}          – Xóa thư mục (cascade)
──────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from dependencies import get_current_user
from models import User
from models_folder import Folder, Document
from schemas_folder import (
    FolderCreate, FolderRename, FolderMoveRequest,
    FolderOut, FolderTreeOut, FolderContentsOut, DocumentOut,
)

router = APIRouter(prefix="/api/folders", tags=["Folder"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_folder_or_404(folder_id: int, db: AsyncSession) -> Folder:
    result = await db.execute(select(Folder).where(Folder.FolderID == folder_id))
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Không tìm thấy thư mục")
    return folder


def _folder_out(f: Folder) -> FolderOut:
    return FolderOut(
        folder_id=f.FolderID,
        name=f.Name,
        parent_id=f.ParentID,
        path=f.Path,
        owner_id=f.OwnerID,
        created_at=f.CreatedAt,
        updated_at=f.UpdatedAt,
    )


async def _build_path(parent_id: Optional[int], name: str, db: AsyncSession) -> str:
    """Tính path mới từ parent."""
    if parent_id is None:
        return f"/root/{name}"
    parent = await _get_folder_or_404(parent_id, db)
    return f"{parent.Path}/{name}"


async def _is_descendant(folder_id: int, target_id: int, db: AsyncSession) -> bool:
    """
    Kiểm tra target_id có phải con cháu của folder_id không.
    Dùng để tránh di chuyển folder vào chính con của nó (tạo vòng lặp).
    """
    current_id = target_id
    visited = set()
    while current_id is not None:
        if current_id in visited:
            break
        if current_id == folder_id:
            return True
        visited.add(current_id)
        result = await db.execute(
            select(Folder.ParentID).where(Folder.FolderID == current_id)
        )
        row = result.scalar_one_or_none()
        current_id = row
    return False


async def _update_path_recursive(folder: Folder, new_path: str, db: AsyncSession):
    """
    Cập nhật Path của folder và toàn bộ con cháu khi di chuyển.
    Dùng string replace theo prefix cũ → prefix mới.
    """
    old_prefix = folder.Path
    new_prefix = new_path

    # Cập nhật folder hiện tại
    folder.Path = new_prefix
    folder.UpdatedAt = datetime.utcnow()

    # Cập nhật tất cả folder con (path bắt đầu bằng old_prefix + "/")
    # Dùng bulk update qua SQLAlchemy
    result = await db.execute(
        select(Folder).where(
            Folder.Path.like(f"{old_prefix}/%")
        )
    )
    descendants = result.scalars().all()
    for desc in descendants:
        desc.Path = new_prefix + desc.Path[len(old_prefix):]
        desc.UpdatedAt = datetime.utcnow()

    # Cập nhật path của Document bên trong folder và con cháu
    affected_folder_ids = [folder.FolderID] + [d.FolderID for d in descendants]
    doc_result = await db.execute(
        select(Document).where(Document.FolderID.in_(affected_folder_ids))
    )
    for doc in doc_result.scalars().all():
        if doc.Path.startswith(old_prefix):
            doc.Path = new_prefix + doc.Path[len(old_prefix):]
            doc.UpdatedAt = datetime.utcnow()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/", status_code=201)
async def create_folder(
    data: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo thư mục mới. `parent_id=null` → thư mục gốc."""
    # Kiểm tra parent tồn tại
    if data.parent_id:
        await _get_folder_or_404(data.parent_id, db)

    # Kiểm tra trùng tên trong cùng cha
    dup = await db.execute(
        select(Folder).where(
            and_(Folder.ParentID == data.parent_id, Folder.Name == data.name)
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Đã tồn tại thư mục cùng tên trong thư mục cha")

    path = await _build_path(data.parent_id, data.name, db)

    folder = Folder(
        Name=data.name,
        ParentID=data.parent_id,
        Path=path,
        OwnerID=current_user.UserID,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)

    return {"success": True, "message": "Tạo thư mục thành công", "data": _folder_out(folder)}


@router.get("/")
async def list_root_folders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách thư mục gốc (không có cha) của người dùng hiện tại."""
    result = await db.execute(
        select(Folder)
        .where(and_(Folder.ParentID == None, Folder.OwnerID == current_user.UserID))
        .order_by(Folder.Name)
    )
    folders = result.scalars().all()
    return {"success": True, "data": [_folder_out(f) for f in folders]}


@router.get("/{folder_id}")
async def get_folder_contents(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nội dung thư mục: danh sách thư mục con + tài liệu bên trong."""
    folder = await _get_folder_or_404(folder_id, db)

    # Sub-folders
    sub_result = await db.execute(
        select(Folder).where(Folder.ParentID == folder_id).order_by(Folder.Name)
    )
    subfolders = sub_result.scalars().all()

    # Documents
    doc_result = await db.execute(
        select(Document).where(Document.FolderID == folder_id).order_by(Document.Name)
    )
    documents = doc_result.scalars().all()

    return {
        "success": True,
        "data": {
            "folder":     _folder_out(folder),
            "subfolders": [_folder_out(f) for f in subfolders],
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
            ],
        },
    }


@router.get("/{folder_id}/tree")
async def get_folder_tree(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Cây thư mục đệ quy từ folder_id trở xuống."""
    async def build_tree(fid: int) -> dict:
        folder = await _get_folder_or_404(fid, db)
        child_result = await db.execute(
            select(Folder).where(Folder.ParentID == fid).order_by(Folder.Name)
        )
        children = child_result.scalars().all()
        return {
            **_folder_out(folder).model_dump(),
            "children": [await build_tree(c.FolderID) for c in children],
        }

    return {"success": True, "data": await build_tree(folder_id)}


@router.patch("/{folder_id}/rename")
async def rename_folder(
    folder_id: int,
    data: FolderRename,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đổi tên thư mục và cập nhật path của toàn bộ con cháu."""
    folder = await _get_folder_or_404(folder_id, db)

    if folder.OwnerID != current_user.UserID:
        raise HTTPException(status_code=403, detail="Không có quyền đổi tên thư mục này")

    if folder.Name == data.name:
        return {"success": True, "message": "Tên không thay đổi", "data": _folder_out(folder)}

    # Kiểm tra trùng tên trong cùng cha
    dup = await db.execute(
        select(Folder).where(
            and_(
                Folder.ParentID == folder.ParentID,
                Folder.Name == data.name,
                Folder.FolderID != folder_id,
            )
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Đã tồn tại thư mục cùng tên trong thư mục cha")

    # Tính path mới
    if folder.ParentID:
        parent = await _get_folder_or_404(folder.ParentID, db)
        new_path = f"{parent.Path}/{data.name}"
    else:
        new_path = f"/root/{data.name}"

    await _update_path_recursive(folder, new_path, db)
    folder.Name = data.name
    await db.commit()
    await db.refresh(folder)

    return {"success": True, "message": "Đổi tên thành công", "data": _folder_out(folder)}


# ⭐ ENDPOINT CHÍNH: DI CHUYỂN THƯ MỤC
@router.patch("/{folder_id}/move")
async def move_folder(
    folder_id: int,
    data: FolderMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Di chuyển thư mục sang thư mục cha mới.

    Body:
      - `target_parent_id` (int | null): ID thư mục cha đích.
        Truyền `null` để chuyển lên root.

    Logic:
      1. Kiểm tra folder tồn tại & quyền sở hữu.
      2. Kiểm tra target_parent tồn tại (nếu không null).
      3. Chặn di chuyển vào chính nó hoặc con cháu của nó (tránh vòng lặp).
      4. Kiểm tra trùng tên trong thư mục đích.
      5. Cập nhật ParentID + Path của folder VÀ toàn bộ con cháu (cascade).
    """
    folder = await _get_folder_or_404(folder_id, db)

    # Quyền sở hữu
    if folder.OwnerID != current_user.UserID:
        raise HTTPException(status_code=403, detail="Không có quyền di chuyển thư mục này")

    # Không cho di chuyển vào chính nó
    if data.target_parent_id == folder_id:
        raise HTTPException(status_code=400, detail="Không thể di chuyển thư mục vào chính nó")

    # Không cho di chuyển nếu cha hiện tại = cha đích (không có gì thay đổi)
    if folder.ParentID == data.target_parent_id:
        return {"success": True, "message": "Thư mục đã ở vị trí này", "data": _folder_out(folder)}

    # Kiểm tra target_parent tồn tại
    if data.target_parent_id is not None:
        await _get_folder_or_404(data.target_parent_id, db)

        # Chặn di chuyển vào con cháu (sẽ tạo vòng lặp)
        if await _is_descendant(folder_id, data.target_parent_id, db):
            raise HTTPException(
                status_code=400,
                detail="Không thể di chuyển thư mục vào thư mục con của nó"
            )

    # Kiểm tra trùng tên trong thư mục đích
    dup = await db.execute(
        select(Folder).where(
            and_(
                Folder.ParentID == data.target_parent_id,
                Folder.Name == folder.Name,
                Folder.FolderID != folder_id,
            )
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f'Đã tồn tại thư mục tên "{folder.Name}" trong thư mục đích'
        )

    # Tính path mới
    new_path = await _build_path(data.target_parent_id, folder.Name, db)

    # Cập nhật path đệ quy (folder + tất cả con cháu + documents)
    await _update_path_recursive(folder, new_path, db)

    # Cập nhật parent
    folder.ParentID = data.target_parent_id
    folder.UpdatedAt = datetime.utcnow()

    await db.commit()
    await db.refresh(folder)

    return {
        "success": True,
        "message": "Di chuyển thư mục thành công",
        "data": _folder_out(folder),
    }


@router.delete("/{folder_id}", status_code=200)
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa thư mục và toàn bộ con cháu (cascade theo DB)."""
    folder = await _get_folder_or_404(folder_id, db)

    if folder.OwnerID != current_user.UserID:
        raise HTTPException(status_code=403, detail="Không có quyền xóa thư mục này")

    await db.delete(folder)
    await db.commit()
    return {"success": True, "message": "Xóa thư mục thành công"}