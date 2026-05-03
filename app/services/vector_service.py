# app/services/vector_service.py
"""
Vector Service - Cross-document search with hybrid retrieval + reranking.
Multilingual embeddings (Arabic + English) with sentence-transformers.

Features:
1. Semantic search (embedding similarity)
2. Keyword search (PostgreSQL full-text)
3. Cross-encoder reranking (BAAI/bge-reranker-base)
4. Cross-document relationship discovery
5. Returns results from multiple documents
"""
from sqlalchemy import select, delete, and_, func, text, or_
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder

from app.config import get_settings
from app.models.database import DocumentChunk, SyncSessionLocal

settings = get_settings()


class SentenceTransformerVectorService:
    """Multilingual sentence-transformers for Arabic + English embeddings."""

    def __init__(self):
        import os

        # Check for offline model path
        model_path = settings.EMBEDDING_MODEL
        if settings.HF_MODELS_OFFLINE and settings.HF_MODELS_PATH:
            local_path = os.path.join(settings.HF_MODELS_PATH, settings.EMBEDDING_MODEL)
            if os.path.exists(local_path):
                model_path = local_path
                print(f"[EMBED] Using offline model: {local_path}")
            else:
                print(f"[EMBED] Offline model not found at {local_path}, downloading...")

        print(f"[EMBED] Loading: {model_path}")
        self._embeddings = HuggingFaceEmbeddings(
            model_name=model_path,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.embedding_dim = settings.EMBEDDING_DIMENSION
        print(f"[EMBED] Loaded! Dim: {self.embedding_dim}")

    def encode_question(self, question: str) -> list[float]:
        return self._embeddings.embed_query(question)

    def encode_context(self, context: str) -> list[float]:
        return self._embeddings.embed_query(context)

    def encode_contexts_batch(self, contexts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(contexts)


class VectorService:
    """
    Main vector service with HYBRID search:
    - Semantic: Find similar meaning across all documents
    - Keyword: Find exact matches for names, IDs, terms
    - Cross-document: Returns results from multiple sources
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not VectorService._initialized:
            self._initialize()
            VectorService._initialized = True
    
    def _initialize(self):
        import os

        print("=" * 60)
        print("  VECTOR SERVICE - Multilingual Cross-Document Search")
        print("=" * 60)

        self._encoder = SentenceTransformerVectorService()
        self.embedding_dim = self._encoder.embedding_dim

        # Load cross-encoder reranker
        reranker_path = settings.RERANKER_MODEL
        if settings.HF_MODELS_OFFLINE and settings.HF_MODELS_PATH:
            local_path = os.path.join(settings.HF_MODELS_PATH, settings.RERANKER_MODEL)
            if os.path.exists(local_path):
                reranker_path = local_path
                print(f"[RERANK] Using offline model: {local_path}")

        try:
            print(f"[RERANK] Loading: {reranker_path}")
            self._reranker = CrossEncoder(reranker_path)
            print(f"[RERANK] Loaded!")
        except Exception as e:
            print(f"[RERANK] WARNING: Failed to load reranker: {e}")
            print(f"[RERANK] Search will work without reranking")
            self._reranker = None

        print("=" * 60)
    
    def _get_query_embedding(self, query: str) -> list[float]:
        return self._encoder.encode_question(query)
    
    def _get_context_embedding(self, context: str) -> list[float]:
        return self._encoder.encode_context(context)
    
    def _get_context_embeddings_batch(self, contexts: list[str]) -> list[list[float]]:
        return self._encoder.encode_contexts_batch(contexts)
    
    def add_documents(self, user_id: str, document_id: str, chunks: list[Document]) -> int:
        """Add document chunks to vector store."""
        if not chunks:
            return 0
        
        print(f"[VECTOR] Adding {len(chunks)} chunks...")
        
        texts = [chunk.page_content for chunk in chunks]
        embeddings = self._get_context_embeddings_batch(texts)
        
        try:
            with SyncSessionLocal() as db:
                db_chunks = []
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    db_chunk = DocumentChunk(
                        document_id=document_id,
                        user_id=user_id,
                        content=chunk.page_content,
                        embedding=embedding,
                        chunk_index=i,
                        chunk_metadata={
                            **chunk.metadata,
                            "document_id": document_id,
                            "chunk_index": i,
                        }
                    )
                    db_chunks.append(db_chunk)
                
                db.add_all(db_chunks)
                db.commit()
                print(f"[VECTOR] ✓ Saved {len(chunks)} chunks")
                
        except Exception as e:
            print(f"[VECTOR] ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        return len(chunks)
    
    def search(
        self,
        user_id: str,
        query: str,
        document_ids: list[str] = None,
        k: int = None
    ) -> list[Document]:
        """
        HYBRID SEARCH across all documents.
        
        1. Keyword search (PostgreSQL full-text or ILIKE)
        2. Semantic search (vector similarity)
        3. Combine results from multiple documents
        
        Returns chunks from ANY matching document.
        """
        import re
        
        k = k or settings.RETRIEVAL_K
        
        print(f"[SEARCH] Query: '{query[:80]}{'...' if len(query) > 80 else ''}'")
        print(f"[SEARCH] Scope: {len(document_ids) if document_ids else 'ALL'} docs, Top {k}")
        
        query_embedding = self._get_query_embedding(query)
        
        with SyncSessionLocal() as db:
            # Base filter
            if document_ids:
                base_filter = and_(
                    DocumentChunk.user_id == user_id,
                    DocumentChunk.document_id.in_(document_ids)
                )
            else:
                base_filter = DocumentChunk.user_id == user_id
            
            # =================================================================
            # STEP 1: Keyword Search (finds exact matches)
            # =================================================================
            keyword_results = []
            
            # Extract search terms (words 3+ chars, no pure stopwords)
            words = re.findall(r'\b\w{3,}\b', query.lower())
            # Simple filter: remove very common words
            common = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'were', 'they', 'this', 'that', 'with', 'from', 'what', 'which', 'when', 'where', 'who', 'how', 'why', 'will', 'would', 'could', 'should', 'there', 'their', 'about', 'into', 'does', 'did', 'get', 'got', 'give', 'make', 'just', 'only', 'come', 'could', 'than', 'like', 'other', 'then', 'its', 'also', 'these', 'more', 'some', 'very', 'after', 'most', 'made', 'find', 'here', 'many', 'such', 'way', 'each', 'she', 'him', 'his', 'may', 'any', 'being', 'use', 'using'}
            keywords = [w for w in words if w not in common][:5]
            
            if keywords:
                print(f"[SEARCH] Keywords: {keywords}")
                
                # Build OR conditions for keyword search
                conditions = [DocumentChunk.content.ilike(f'%{kw}%') for kw in keywords]
                
                keyword_chunks = db.execute(
                    select(DocumentChunk)
                    .where(and_(base_filter, or_(*conditions)))
                    .limit(k * 3)
                ).scalars().all()
                
                # Score by number of keyword matches
                scored = []
                for chunk in keyword_chunks:
                    content_lower = chunk.content.lower()
                    score = sum(1 for kw in keywords if kw in content_lower)
                    scored.append((chunk, score))
                
                scored.sort(key=lambda x: x[1], reverse=True)
                keyword_results = [item[0] for item in scored]
                
                print(f"[SEARCH] Keyword matches: {len(keyword_results)}")
            
            # =================================================================
            # STEP 2: Semantic Search (finds similar meaning)
            # =================================================================
            semantic_results = db.execute(
                select(DocumentChunk)
                .where(base_filter)
                .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
                .limit(k)
            ).scalars().all()
            
            print(f"[SEARCH] Semantic matches: {len(semantic_results)}")
            
            # =================================================================
            # STEP 3: Combine (keyword first, then semantic)
            # =================================================================
            seen_ids = set()
            combined = []
            
            for chunk in keyword_results:
                if chunk.id not in seen_ids:
                    combined.append(chunk)
                    seen_ids.add(chunk.id)
            
            for chunk in semantic_results:
                if chunk.id not in seen_ids:
                    combined.append(chunk)
                    seen_ids.add(chunk.id)
            
            # =================================================================
            # STEP 4: Rerank with cross-encoder (if available)
            # =================================================================
            top_n = settings.RERANKER_TOP_N
            if self._reranker and len(combined) > top_n:
                pairs = [(query, chunk.content) for chunk in combined]
                try:
                    scores = self._reranker.predict(pairs)
                    scored_chunks = list(zip(combined, scores))
                    scored_chunks.sort(key=lambda x: x[1], reverse=True)
                    results = [chunk for chunk, score in scored_chunks[:top_n]]
                    print(f"[SEARCH] Reranked {len(combined)} → {len(results)} chunks")
                except Exception as e:
                    print(f"[SEARCH] Reranker error, falling back: {e}")
                    results = combined[:top_n]
            else:
                results = combined[:top_n]

            # Log sources (shows cross-document results)
            sources = {}
            for chunk in results:
                src = chunk.chunk_metadata.get('source', chunk.document_id[:8])
                sources[src] = sources.get(src, 0) + 1

            print(f"[SEARCH] Results: {len(results)} chunks from {len(sources)} documents")
            for src, count in sources.items():
                print(f"[SEARCH]   • {src}: {count} chunks")
            
            # Convert to LangChain Documents
            documents = []
            for chunk in results:
                doc = Document(
                    page_content=chunk.content,
                    metadata={
                        **(chunk.chunk_metadata or {}),
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                    }
                )
                documents.append(doc)
            
            return documents
    
    def delete_document(self, user_id: str, document_id: str):
        """Delete all chunks for a document."""
        with SyncSessionLocal() as db:
            db.execute(
                delete(DocumentChunk).where(
                    and_(
                        DocumentChunk.user_id == user_id,
                        DocumentChunk.document_id == document_id
                    )
                )
            )
            db.commit()
            print(f"[VECTOR] Deleted chunks for {document_id[:8]}...")
    
    def get_document_chunks(self, document_id: str) -> list[DocumentChunk]:
        """Get all chunks for a document."""
        with SyncSessionLocal() as db:
            results = db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            ).scalars().all()
            return results
    
    def get_chunk_count(self, user_id: str) -> int:
        """Get total chunks for user."""
        with SyncSessionLocal() as db:
            result = db.execute(
                select(func.count(DocumentChunk.id))
                .where(DocumentChunk.user_id == user_id)
            ).scalar()
            return result or 0

    def get_full_document_text(self, document_ids: list[str]) -> tuple[str, int]:
        """Get concatenated text of all chunks for given documents, ordered by chunk_index.
        Returns (full_text, total_chars)."""
        with SyncSessionLocal() as db:
            chunks = db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id.in_(document_ids))
                .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
            ).scalars().all()

            if not chunks:
                return "", 0

            parts = []
            current_doc_id = None
            for chunk in chunks:
                if chunk.document_id != current_doc_id:
                    current_doc_id = chunk.document_id
                    src = chunk.chunk_metadata.get('source', chunk.document_id[:8])
                    parts.append(f"\n--- {src} ---\n")
                parts.append(chunk.content)

            full_text = "\n".join(parts)
            return full_text, len(full_text)


# Singleton
vector_service = VectorService()