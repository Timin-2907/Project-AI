# models_folder.py  –  Thêm vào models.py hiện có

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, BigInteger, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class Folder(Base):
    __tablename__ = "Folder"

    FolderID  = Column(Integer, primary_key=True, autoincrement=True)
    Name      = Column(String(255), nullable=False)
    ParentID  = Column(Integer, ForeignKey("Folder.FolderID", ondelete="CASCADE"), nullable=True)
    Path      = Column(Text, nullable=False)       # /root/toan/chuong1
    OwnerID   = Column(Integer, ForeignKey("User.UserID", ondelete="SET NULL"), nullable=True)
    CreatedAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("ParentID", "Name", name="uq_folder_name_in_parent"),
    )

    parent   = relationship("Folder", remote_side="Folder.FolderID", back_populates="children")
    children = relationship("Folder", back_populates="parent", cascade="all, delete")
    owner    = relationship("User", foreign_keys=[OwnerID])
    documents = relationship("Document", back_populates="folder")


class Document(Base):
    __tablename__ = "Document"

    DocumentID = Column(Integer, primary_key=True, autoincrement=True)
    FolderID   = Column(Integer, ForeignKey("Folder.FolderID", ondelete="SET NULL"), nullable=True)
    Name       = Column(String(255), nullable=False)
    Path       = Column(Text, nullable=False)
    MimeType   = Column(String(100))
    Size       = Column(BigInteger, default=0)
    OwnerID    = Column(Integer, ForeignKey("User.UserID", ondelete="SET NULL"), nullable=True)
    CreatedAt  = Column(DateTime, default=datetime.utcnow, nullable=False)
    UpdatedAt  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    folder = relationship("Folder", back_populates="documents")
    owner  = relationship("User", foreign_keys=[OwnerID])