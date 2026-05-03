# app/services/__init__.py
# Import torch FIRST to prevent DLL conflicts on Windows
try:
    import torch
except ImportError:
    pass

from app.services.vector_service import vector_service
from app.services.document_service import document_service
from app.services.chat_service import chat_service

__all__ = ['vector_service', 'document_service', 'chat_service']
