from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class CodeCollection(Base):
    __tablename__ = "codecollections"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    git_url = Column(String(500), nullable=False)
    description = Column(Text)
    owner = Column(String(100))
    owner_email = Column(String(255))
    owner_icon = Column(String(500))
    git_ref = Column(String(50), default="main")
    last_synced = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    codebundles = relationship("Codebundle", back_populates="codecollection", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CodeCollection(id={self.id}, name='{self.name}', slug='{self.slug}')>"
