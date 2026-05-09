# schemas_folder.py

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional


# ─── Folder ───────────────────────────────────────────────────────────────────

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Tên thư mục không được để trống")
        if len(v) > 255:
            raise ValueError("Tên thư mục tối đa 255 ký tự")
        if any(c in v for c in r'\/:*?"<>|'):
            raise ValueError(r'Tên thư mục không được chứa ký tự: \ / : * ? " < > |')
        return v


class FolderRename(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_valid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Tên thư mục không được để trống")
        if any(c in v for c in r'\/:*?"<>|'):
            raise ValueError(r'Tên thư mục không được chứa ký tự đặc biệt')
        return v


class FolderMoveRequest(BaseModel):
    target_parent_id: Optional[int] = None   # None = chuyển về root


class FolderOut(BaseModel):
    folder_id: int
    name: str
    parent_id: Optional[int]
    path: str
    owner_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FolderTreeOut(FolderOut):
    children: list["FolderTreeOut"] = []

FolderTreeOut.model_rebuild()


# ─── Document ─────────────────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    document_id: int
    folder_id: Optional[int]
    name: str
    path: str
    mime_type: Optional[str]
    size: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Folder Contents ──────────────────────────────────────────────────────────

class FolderContentsOut(BaseModel):
    folder: FolderOut
    subfolders: list[FolderOut]
    documents: list[DocumentOut]