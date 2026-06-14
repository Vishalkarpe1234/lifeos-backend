from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from pydantic import BaseModel
import pypdf
import io

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.ai_chat import AIChat, AIMessage
from app.services.ai_service import ai_service
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatCreate(BaseModel):
    title: str
    model: str = "claude-sonnet-4-6"
    module: Optional[str] = None
    system_prompt: Optional[str] = None


class MessageCreate(BaseModel):
    content: str
    role: str = "user"


class ChatRequest(BaseModel):
    chat_id: Optional[int] = None
    message: str
    model: str = "claude-sonnet-4-6"
    system_prompt: Optional[str] = None
    module: Optional[str] = None


class LecturePlanRequest(BaseModel):
    topic: str
    subject: str
    duration_minutes: int = 50


class MCQRequest(BaseModel):
    topic: str
    count: int = 10
    difficulty: str = "medium"


class BlogRequest(BaseModel):
    topic: str
    keywords: List[str] = []
    word_count: int = 800


class ResearchSummaryRequest(BaseModel):
    title: str
    abstract: str


@router.get("/chats")
async def list_chats(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    items = (await db.execute(select(AIChat).order_by(desc(AIChat.updated_at)))).scalars().all()
    return {"items": items}


@router.post("/chats", status_code=201)
async def create_chat(data: ChatCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    chat = AIChat(**data.model_dump())
    db.add(chat)
    await db.flush()
    await db.refresh(chat)
    return chat


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    chat = (await db.execute(select(AIChat).where(AIChat.id == chat_id))).scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = (await db.execute(select(AIMessage).where(AIMessage.chat_id == chat_id).order_by(AIMessage.created_at))).scalars().all()
    return {"chat": chat, "messages": messages}


@router.post("/chat")
async def chat_with_ai(data: ChatRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    if not data.chat_id:
        chat = AIChat(title=data.message[:50], model=data.model, module=data.module)
        db.add(chat)
        await db.flush()
        chat_id = chat.id
    else:
        chat_id = data.chat_id
        chat = (await db.execute(select(AIChat).where(AIChat.id == chat_id))).scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

    prev_messages = (await db.execute(
        select(AIMessage).where(AIMessage.chat_id == chat_id).order_by(AIMessage.created_at)
    )).scalars().all()

    messages = [{"role": m.role, "content": m.content} for m in prev_messages]
    messages.append({"role": "user", "content": data.message})

    try:
        result = await ai_service.chat(
            messages=messages,
            system_prompt=data.system_prompt,
            model=data.model,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    user_msg = AIMessage(chat_id=chat_id, role="user", content=data.message)
    ai_msg = AIMessage(
        chat_id=chat_id,
        role="assistant",
        content=result["content"],
        tokens=result.get("output_tokens"),
    )
    db.add(user_msg)
    db.add(ai_msg)
    chat.total_tokens = (chat.total_tokens or 0) + (result.get("input_tokens", 0) + result.get("output_tokens", 0))
    await db.flush()

    return {"chat_id": chat_id, "response": result["content"], "tokens": result.get("output_tokens")}


@router.delete("/chats/{chat_id}", response_model=SuccessResponse)
async def delete_chat(chat_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    chat = (await db.execute(select(AIChat).where(AIChat.id == chat_id))).scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    await db.execute(select(AIMessage).where(AIMessage.chat_id == chat_id))
    messages = (await db.execute(select(AIMessage).where(AIMessage.chat_id == chat_id))).scalars().all()
    for m in messages:
        await db.delete(m)
    await db.delete(chat)
    return SuccessResponse(message="Chat deleted")


@router.post("/generate/lecture-plan")
async def generate_lecture_plan(data: LecturePlanRequest, current_user=Depends(get_current_user)):
    try:
        content = await ai_service.generate_lecture_plan(data.topic, data.subject, data.duration_minutes)
        return {"content": content}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/generate/mcqs")
async def generate_mcqs(data: MCQRequest, current_user=Depends(get_current_user)):
    try:
        content = await ai_service.generate_mcqs(data.topic, data.count, data.difficulty)
        return {"content": content}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/generate/blog")
async def generate_blog(data: BlogRequest, current_user=Depends(get_current_user)):
    try:
        content = await ai_service.generate_blog_post(data.topic, data.keywords, data.word_count)
        return {"content": content}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/generate/research-summary")
async def generate_research_summary(data: ResearchSummaryRequest, current_user=Depends(get_current_user)):
    try:
        content = await ai_service.generate_research_summary(data.abstract, data.title)
        return {"content": content}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/summarize/pdf")
async def summarize_pdf(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files accepted")
    content = await file.read()
    reader = pypdf.PdfReader(io.BytesIO(content))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")
    try:
        summary = await ai_service.summarize_pdf_text(text)
        return {"summary": summary, "pages": len(reader.pages), "char_count": len(text)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
