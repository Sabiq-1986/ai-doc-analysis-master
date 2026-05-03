# app/services/chat_service.py
"""Chat Service with STREAMING support for Ollama LLM."""
import json
import httpx
import asyncio
from typing import Optional, List, AsyncGenerator
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.config import get_settings
from app.models.database import ChatSession, ChatMessage, Document as DBDocument
from app.services.vector_service import vector_service
from app.services.excel_query_service import excel_query_service

settings = get_settings()


class ChatService:
    """Chat service with streaming LLM responses."""
    
    def __init__(self):
        self.ollama_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
        print(f"[CHAT] Ollama: {self.ollama_url}, Model: {self.model}")
    
    def _build_prompt(self, query: str, context_docs: List, chat_history: List = None) -> str:
        """Build prompt with context and history."""
        
        if context_docs:
            context_parts = []
            for i, doc in enumerate(context_docs, 1):
                source = doc.metadata.get('source', 'Unknown')
                context_parts.append(f"[Document {i}: {source}]\n{doc.page_content}")
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No relevant documents found."
        
        history_text = ""
        if chat_history:
            history_parts = []
            for msg in chat_history[-6:]:
                role = "User" if msg.role == "user" else "Assistant"
                history_parts.append(f"{role}: {msg.content[:500]}")
            if history_parts:
                history_text = "\n".join(history_parts) + "\n\n"
        
        prompt = f"""You are a helpful bilingual assistant (English and Arabic) that answers questions based on the provided documents.

CONTEXT FROM DOCUMENTS:
{context}

{f"RECENT CONVERSATION:{chr(10)}{history_text}" if history_text else ""}
USER QUESTION: {query}

INSTRUCTIONS:
- Answer based on the document context. Be concise and accurate.
- IMPORTANT: Respond in the SAME LANGUAGE as the user's question. If the question is in Arabic, respond in Arabic. If in English, respond in English.
- Present information in a natural, user-friendly way.
- For identity documents, present details naturally (e.g., "This is a passport for [Name], document number [Number], valid until [Date]").
- For Arabic documents, preserve Arabic text and names accurately.

ANSWER:"""

        return prompt

    def _build_full_context_prompt(self, query: str, full_content: str, filenames: list, chat_history: list = None) -> str:
        """Build prompt for full context mode (complete document, no RAG)."""
        history_text = ""
        if chat_history:
            history_parts = []
            for msg in chat_history[-6:]:
                role = "User" if msg.role == "user" else "Assistant"
                history_parts.append(f"{role}: {msg.content[:500]}")
            if history_parts:
                history_text = "\n".join(history_parts) + "\n\n"

        files_str = ", ".join(filenames)

        return f"""You are a helpful bilingual assistant (English and Arabic). You have the COMPLETE content of the following document(s): {files_str}

FULL DOCUMENT CONTENT:
{full_content}

{f"RECENT CONVERSATION:{chr(10)}{history_text}" if history_text else ""}
USER QUESTION: {query}

INSTRUCTIONS:
- You have the COMPLETE document — not fragments. Use ALL of it to answer accurately.
- IMPORTANT: Respond in the SAME LANGUAGE as the user's question.
- For tables and structured data, preserve formatting and be precise with numbers.
- For Arabic documents, preserve Arabic text and names accurately.
- Be concise and directly answer the question.

ANSWER:"""

    async def _get_document_filenames(self, db: AsyncSession, document_ids: list) -> list:
        """Get filenames for document IDs."""
        if not document_ids:
            return []
        result = await db.execute(
            select(DBDocument).where(DBDocument.id.in_(document_ids))
        )
        docs = list(result.scalars().all())
        return [d.filename for d in docs]

    async def check_ollama(self) -> dict:
        """Check if Ollama is running and model is available."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code != 200:
                    return {"ok": False, "error": f"Ollama returned {resp.status_code}"}
                
                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]
                
                # Check if our model exists
                model_found = self.model in model_names or f"{self.model}:latest" in model_names
                if not model_found:
                    # Check base name
                    base = self.model.split(":")[0]
                    model_found = any(m.startswith(base) for m in model_names)
                
                if not model_found:
                    return {
                        "ok": False, 
                        "error": f"Model '{self.model}' not found. Available: {model_names}",
                        "models": model_names
                    }
                
                return {"ok": True, "models": model_names}
        except httpx.ConnectError:
            return {"ok": False, "error": "Cannot connect to Ollama. Is it running? (ollama serve)"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def stream_chat(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: str,
        question: str
    ) -> AsyncGenerator[str, None]:
        """Stream chat response token by token."""
        
        try:
            # Get chat session
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id
                )
            )
            session = result.scalar_one_or_none()
            
            if not session:
                yield json.dumps({"type": "error", "content": "Session not found"})
                return

            # Check if session has Excel files — use pandas instead of embeddings
            excel_docs = await self._get_excel_files(db, session.document_ids)
            if excel_docs:
                print(f"[CHAT] Found {len(excel_docs)} Excel file(s), using pandas query")
                excel_doc = excel_docs[0]
                query_result = await excel_query_service.query_excel(
                    excel_doc.file_path, question
                )
                if query_result["success"]:
                    # Save user message
                    user_msg = ChatMessage(
                        session_id=session_id, role="user", content=question
                    )
                    db.add(user_msg)
                    await db.commit()

                    yield json.dumps({"type": "sources", "content": [{"filename": excel_doc.filename}]})

                    # Format with LLM for natural language
                    natural_response = await self._format_excel_response(
                        question, query_result["answer"], excel_doc.filename
                    )

                    # Save assistant message
                    assistant_msg = ChatMessage(
                        session_id=session_id, role="assistant",
                        content=natural_response, sources=[excel_doc.filename]
                    )
                    db.add(assistant_msg)

                    if not (await db.execute(
                        select(ChatMessage).where(
                            ChatMessage.session_id == session_id,
                            ChatMessage.role == "user"
                        )
                    )).scalars().first():
                        title = question[:50] + ("..." if len(question) > 50 else "")
                        await db.execute(
                            update(ChatSession)
                            .where(ChatSession.id == session_id)
                            .values(title=title, updated_at=datetime.utcnow())
                        )

                    await db.commit()

                    yield json.dumps({"type": "token", "content": natural_response})
                    yield json.dumps({"type": "done", "content": natural_response})
                    print("[CHAT] Excel query complete (pandas path)")
                    return
                else:
                    print(f"[CHAT] Excel query failed, falling back to RAG")

            # Get chat history
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(10)
            )
            history = list(result.scalars().all())
            history.reverse()

            # ============================================================
            # FULL CONTEXT MODE: If document fits, skip RAG entirely
            # ============================================================
            full_text, total_chars = vector_service.get_full_document_text(
                session.document_ids
            )
            if full_text and total_chars <= settings.FULL_CONTEXT_MAX_CHARS:
                print(f"[CHAT] Using FULL CONTEXT mode ({total_chars:,} chars)")
                filenames = await self._get_document_filenames(db, session.document_ids)
                prompt = self._build_full_context_prompt(
                    question, full_text, filenames, history
                )

                # Save user message
                user_msg = ChatMessage(
                    session_id=session_id, role="user", content=question
                )
                db.add(user_msg)
                await db.commit()

                # Send sources
                sources = [{"filename": f} for f in filenames]
                yield json.dumps({"type": "sources", "content": sources})

                # Check Ollama
                check = await self.check_ollama()
                if not check["ok"]:
                    yield json.dumps({"type": "error", "content": check['error']})
                    return

                # Stream from Ollama
                full_response = ""
                try:
                    async with httpx.AsyncClient() as client:
                        async with client.stream(
                            "POST",
                            f"{self.ollama_url}/api/generate",
                            json={
                                "model": self.model,
                                "prompt": prompt,
                                "stream": True,
                                "options": {"temperature": 0.7, "top_p": 0.9}
                            },
                            timeout=httpx.Timeout(self.timeout, connect=10.0)
                        ) as response:
                            if response.status_code != 200:
                                error_body = await response.aread()
                                try:
                                    error_msg = json.loads(error_body).get("error", error_body.decode())
                                except Exception:
                                    error_msg = f"HTTP {response.status_code}"
                                yield json.dumps({"type": "error", "content": f"Ollama error: {error_msg}"})
                                return

                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                try:
                                    data = json.loads(line)
                                    if "error" in data:
                                        yield json.dumps({"type": "error", "content": data['error']})
                                        return
                                    token = data.get("response", "")
                                    if token:
                                        full_response += token
                                        yield json.dumps({"type": "token", "content": token})
                                        await asyncio.sleep(0.001)
                                    if data.get("done", False):
                                        break
                                except json.JSONDecodeError:
                                    continue
                except (httpx.ConnectError, httpx.TimeoutException, Exception) as e:
                    yield json.dumps({"type": "error", "content": str(e)})
                    return

                # Save assistant message
                if full_response:
                    assistant_msg = ChatMessage(
                        session_id=session_id, role="assistant",
                        content=full_response, sources=[s["filename"] for s in sources]
                    )
                    db.add(assistant_msg)
                    if not history:
                        title = question[:50] + ("..." if len(question) > 50 else "")
                        await db.execute(
                            update(ChatSession).where(ChatSession.id == session_id)
                            .values(title=title, updated_at=datetime.utcnow())
                        )
                    else:
                        await db.execute(
                            update(ChatSession).where(ChatSession.id == session_id)
                            .values(updated_at=datetime.utcnow())
                        )
                    await db.commit()

                yield json.dumps({"type": "done", "content": full_response})
                print("[CHAT] Full context stream complete")
                return

            # ============================================================
            # RAG MODE: Document too large, use retrieval + reranking
            # ============================================================
            print(f"[CHAT] Using RAG mode (doc {total_chars:,} chars > {settings.FULL_CONTEXT_MAX_CHARS:,} limit)")
            print(f"[CHAT] Searching documents for: {question[:50]}...")
            context_docs = vector_service.search(
                user_id=user_id,
                query=question,
                document_ids=session.document_ids,
                k=settings.RETRIEVAL_K
            )
            print(f"[CHAT] Found {len(context_docs)} relevant chunks")

            # Build prompt
            prompt = self._build_prompt(question, context_docs, history)
            
            # Save user message
            user_msg = ChatMessage(
                session_id=session_id,
                role="user",
                content=question
            )
            db.add(user_msg)
            await db.commit()
            
            # Send sources first
            sources = []
            seen = set()
            for doc in context_docs:
                src = doc.metadata.get('source', 'Unknown')
                if src not in seen:
                    sources.append({"filename": src})
                    seen.add(src)
            
            print(f"[CHAT] Sending sources: {sources}")
            yield json.dumps({"type": "sources", "content": sources})
            
            # Check Ollama before calling
            print(f"[CHAT] Checking Ollama...")
            check = await self.check_ollama()
            if not check["ok"]:
                print(f"[CHAT] ✗ Ollama check failed: {check['error']}")
                yield json.dumps({"type": "error", "content": check['error']})
                return
            print(f"[CHAT] ✓ Ollama OK, calling model: {self.model}")
            
            # Stream from Ollama using httpx
            full_response = ""
            
            try:
                async with httpx.AsyncClient() as client:
                    print(f"[CHAT] Calling Ollama...")
                    
                    async with client.stream(
                        "POST",
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": self.model,
                            "prompt": prompt,
                            "stream": True,
                            "options": {"temperature": 0.7, "top_p": 0.9}
                        },
                        timeout=httpx.Timeout(self.timeout, connect=10.0)
                    ) as response:
                        
                        print(f"[CHAT] Ollama response status: {response.status_code}")
                        
                        # CHECK FOR ERROR STATUS CODES
                        if response.status_code != 200:
                            error_body = await response.aread()
                            try:
                                error_json = json.loads(error_body)
                                error_msg = error_json.get("error", str(error_body.decode()))
                            except:
                                error_msg = error_body.decode() if error_body else f"HTTP {response.status_code}"
                            
                            print(f"[CHAT] ✗ Ollama error: {error_msg}")
                            yield json.dumps({"type": "error", "content": f"Ollama error: {error_msg}"})
                            return
                        
                        token_count = 0
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                
                                # Check for error in stream
                                if "error" in data:
                                    print(f"[CHAT] ✗ Stream error: {data['error']}")
                                    yield json.dumps({"type": "error", "content": data['error']})
                                    return
                                
                                token = data.get("response", "")
                                if token:
                                    full_response += token
                                    token_count += 1
                                    yield json.dumps({"type": "token", "content": token})
                                    
                                    if token_count % 20 == 0:
                                        print(f"[CHAT] Sent {token_count} tokens...")
                                    
                                    await asyncio.sleep(0.001)
                                
                                if data.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
                        
                        print(f"[CHAT] Generation complete. Total tokens: {token_count}")
                        
            except httpx.ConnectError:
                error_msg = f"Cannot connect to Ollama at {self.ollama_url}. Is it running?"
                print(f"[CHAT] ✗ {error_msg}")
                yield json.dumps({"type": "error", "content": error_msg})
                return
            except httpx.TimeoutException:
                error_msg = "Request timed out. Model might be loading or prompt too long."
                print(f"[CHAT] ✗ {error_msg}")
                yield json.dumps({"type": "error", "content": error_msg})
                return
            except Exception as e:
                error_msg = f"Ollama error: {type(e).__name__}: {str(e)}"
                print(f"[CHAT] ✗ {error_msg}")
                yield json.dumps({"type": "error", "content": error_msg})
                return
            
            # Save assistant message
            if full_response:
                assistant_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    sources=[s["filename"] for s in sources]
                )
                db.add(assistant_msg)
                
                if not history:
                    title = question[:50] + ("..." if len(question) > 50 else "")
                    await db.execute(
                        update(ChatSession)
                        .where(ChatSession.id == session_id)
                        .values(title=title, updated_at=datetime.utcnow())
                    )
                else:
                    await db.execute(
                        update(ChatSession)
                        .where(ChatSession.id == session_id)
                        .values(updated_at=datetime.utcnow())
                    )
                
                await db.commit()
            
            yield json.dumps({"type": "done", "content": full_response})
            print("[CHAT] Stream complete")
            
        except Exception as e:
            print(f"[CHAT] Error: {e}")
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "content": str(e)})
    
    async def _get_excel_files(self, db: AsyncSession, document_ids: List[str]) -> List[DBDocument]:
        """Get Excel documents from the session's document list."""
        if not document_ids:
            return []

        excel_extensions = {'.xlsx', '.xls', '.xlsm'}
        result = await db.execute(
            select(DBDocument).where(DBDocument.id.in_(document_ids))
        )
        docs = list(result.scalars().all())
        return [d for d in docs if d.file_type.lower() in excel_extensions]

    async def chat(self, db: AsyncSession, user_id: str, session_id: str, question: str) -> dict:
        """Non-streaming chat with Excel query support."""

        # Get session to check for Excel files
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise Exception("Session not found")

        # Check if session has Excel files
        excel_docs = await self._get_excel_files(db, session.document_ids)

        if excel_docs:
            # Use Excel query service for data analysis
            print(f"[CHAT] Found {len(excel_docs)} Excel file(s), using pandas query")

            # Query the first Excel file (could be extended to handle multiple)
            excel_doc = excel_docs[0]
            query_result = await excel_query_service.query_excel(
                excel_doc.file_path,
                question
            )

            if query_result["success"]:
                # Save user message
                user_msg = ChatMessage(
                    session_id=session_id,
                    role="user",
                    content=question
                )
                db.add(user_msg)

                # Format response with computed data
                computed_answer = query_result["answer"]

                # Use LLM to create a natural language response
                natural_response = await self._format_excel_response(
                    question,
                    computed_answer,
                    excel_doc.filename
                )

                # Save assistant message
                assistant_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=natural_response,
                    sources=[excel_doc.filename]
                )
                db.add(assistant_msg)

                # Update session
                await db.execute(
                    update(ChatSession)
                    .where(ChatSession.id == session_id)
                    .values(updated_at=datetime.utcnow())
                )
                await db.commit()

                return {
                    "response": natural_response,
                    "sources": [{"filename": excel_doc.filename}]
                }
            else:
                print(f"[CHAT] Excel query failed, falling back to RAG")

        # Fall back to standard RAG approach
        full_response = ""
        sources = []

        async for chunk in self.stream_chat(db, user_id, session_id, question):
            data = json.loads(chunk)
            if data["type"] == "token":
                full_response += data["content"]
            elif data["type"] == "sources":
                sources = data["content"]
            elif data["type"] == "done":
                full_response = data["content"]
            elif data["type"] == "error":
                raise Exception(data["content"])

        return {"response": full_response, "sources": sources}

    async def _format_excel_response(self, question: str, computed_data: str, filename: str) -> str:
        """Use LLM to format computed Excel data into natural language."""
        prompt = f"""You are a helpful assistant. The user asked a question about an Excel spreadsheet, and the system has computed the answer using pandas.

USER QUESTION: {question}

COMPUTED DATA FROM '{filename}':
{computed_data}

Please provide a clear, natural language answer based on this computed data. Be concise and directly answer the question. If the data shows specific numbers or calculations, include them in your response.

ANSWER:"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3}
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", computed_data)
        except Exception as e:
            print(f"[CHAT] Error formatting response: {e}")

        # Fallback to raw computed data
        return f"Based on the data in {filename}:\n\n{computed_data}"
    
    # ============ Session Management ============
    
    async def create_session(self, db: AsyncSession, user_id: str, title: str = "New Chat", document_ids: List[str] = None) -> ChatSession:
        session = ChatSession(user_id=user_id, title=title, document_ids=document_ids or [])
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session
    
    async def get_session(self, db: AsyncSession, session_id: str, user_id: str):
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
        session = result.scalar_one_or_none()
        if not session:
            return None, []
        result = await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()))
        return session, list(result.scalars().all())
    
    async def get_user_sessions(self, db: AsyncSession, user_id: str) -> List[ChatSession]:
        result = await db.execute(select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc()))
        return list(result.scalars().all())
    
    async def update_session_title(self, db: AsyncSession, session_id: str, user_id: str, title: str) -> Optional[ChatSession]:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
        session = result.scalar_one_or_none()
        if session:
            session.title = title
            session.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(session)
        return session
    
    async def delete_session(self, db: AsyncSession, session_id: str, user_id: str) -> bool:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
        session = result.scalar_one_or_none()
        if not session:
            return False
        await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        await db.delete(session)
        await db.commit()
        return True
    
    async def add_documents_to_session(self, db: AsyncSession, session_id: str, user_id: str, document_ids: List[str]) -> ChatSession:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError("Session not found")
        current = set(session.document_ids or [])
        current.update(document_ids)
        session.document_ids = list(current)
        session.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(session)
        return session
    
    async def remove_documents_from_session(self, db: AsyncSession, session_id: str, user_id: str, document_ids: List[str]) -> ChatSession:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError("Session not found")
        current = set(session.document_ids or [])
        current -= set(document_ids)
        session.document_ids = list(current)
        session.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(session)
        return session


chat_service = ChatService()