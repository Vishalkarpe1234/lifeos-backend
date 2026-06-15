import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func

from app.core.database import get_db, AsyncSessionLocal
from app.core.dependencies import get_current_user
from app.core.security import verify_access_token
from app.models.user import User
from app.models.profile import Profile
from app.models.connect import FriendRequest, Friendship, Message
from app.schemas.common import SuccessResponse
from app.services.storage_service import storage_service
from pydantic import BaseModel

router = APIRouter(prefix="/connect", tags=["Connect"])

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,30}$")
ALLOWED_CHAT_FILE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_profile(user_id: int, db: AsyncSession) -> Profile:
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile(user_id=user_id)
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
    return profile


async def _are_friends(user_a: int, user_b: int, db: AsyncSession) -> bool:
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.user1_id == user_a, Friendship.user2_id == user_b),
                and_(Friendship.user1_id == user_b, Friendship.user2_id == user_a),
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def _relationship_status(current_id: int, other_id: int, db: AsyncSession) -> str:
    if await _are_friends(current_id, other_id, db):
        return "friends"
    result = await db.execute(
        select(FriendRequest).where(
            FriendRequest.status == "pending",
            or_(
                and_(FriendRequest.sender_id == current_id, FriendRequest.receiver_id == other_id),
                and_(FriendRequest.sender_id == other_id, FriendRequest.receiver_id == current_id),
            ),
        )
    )
    req = result.scalar_one_or_none()
    if req:
        return "outgoing" if req.sender_id == current_id else "incoming"
    return "none"


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active: dict[int, set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        conns = self.active.get(user_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self.active[user_id]

    async def send_personal(self, user_id: int, data: dict):
        for ws in list(self.active.get(user_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                pass

    def is_online(self, user_id: int) -> bool:
        return user_id in self.active


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Profile (username + bio)
# ---------------------------------------------------------------------------

class ConnectProfileUpdate(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = None


@router.get("/profile")
async def get_connect_profile(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(current_user.id, db)
    return {
        "username": current_user.username,
        "bio": profile.bio,
        "full_name": profile.full_name,
        "profile_photo_url": profile.profile_photo_url,
    }


@router.patch("/profile", response_model=SuccessResponse)
async def update_connect_profile(
    data: ConnectProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.username is not None:
        username = data.username.strip().lower()
        if not USERNAME_RE.match(username):
            raise HTTPException(status_code=400, detail="Username must be 3-30 characters: letters, numbers, underscore only")
        existing = await db.execute(select(User).where(User.username == username, User.id != current_user.id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already taken")
        current_user.username = username

    if data.bio is not None:
        profile = await _get_or_create_profile(current_user.id, db)
        profile.bio = data.bio

    await db.flush()
    return SuccessResponse(message="Profile updated")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@router.get("/search")
async def search_users(q: str = "", current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = q.strip().lower()
    if len(q) < 2:
        return {"items": []}

    result = await db.execute(
        select(User).where(User.username.ilike(f"%{q}%"), User.id != current_user.id, User.username.is_not(None)).limit(20)
    )
    users = result.scalars().all()

    items = []
    for u in users:
        status = await _relationship_status(current_user.id, u.id, db)
        items.append({"id": u.id, "username": u.username, "status": status})
    return {"items": items}


# ---------------------------------------------------------------------------
# Friend requests
# ---------------------------------------------------------------------------

class FriendRequestCreate(BaseModel):
    username: str


@router.post("/friend-requests", status_code=201)
async def send_friend_request(
    data: FriendRequestCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = data.username.strip().lower()
    result = await db.execute(select(User).where(User.username == username))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a friend request to yourself")

    if await _are_friends(current_user.id, target.id, db):
        raise HTTPException(status_code=400, detail="Already friends")

    existing = await db.execute(
        select(FriendRequest).where(
            FriendRequest.status == "pending",
            or_(
                and_(FriendRequest.sender_id == current_user.id, FriendRequest.receiver_id == target.id),
                and_(FriendRequest.sender_id == target.id, FriendRequest.receiver_id == current_user.id),
            ),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A friend request is already pending")

    req = FriendRequest(sender_id=current_user.id, receiver_id=target.id, status="pending")
    db.add(req)
    await db.flush()
    await db.refresh(req)

    await manager.send_personal(target.id, {
        "type": "friend_request",
        "request_id": req.id,
        "from_username": current_user.username,
    })

    return SuccessResponse(message="Friend request sent")


@router.get("/friend-requests")
async def list_friend_requests(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    incoming_result = await db.execute(
        select(FriendRequest, User.username).join(User, User.id == FriendRequest.sender_id)
        .where(FriendRequest.receiver_id == current_user.id, FriendRequest.status == "pending")
    )
    outgoing_result = await db.execute(
        select(FriendRequest, User.username).join(User, User.id == FriendRequest.receiver_id)
        .where(FriendRequest.sender_id == current_user.id, FriendRequest.status == "pending")
    )

    incoming = [{"id": r.id, "user_id": r.sender_id, "username": username, "created_at": str(r.created_at)} for r, username in incoming_result.all()]
    outgoing = [{"id": r.id, "user_id": r.receiver_id, "username": username, "created_at": str(r.created_at)} for r, username in outgoing_result.all()]

    return {"incoming": incoming, "outgoing": outgoing}


class RespondRequest(BaseModel):
    action: str  # "accept" or "reject"


@router.post("/friend-requests/{request_id}/respond", response_model=SuccessResponse)
async def respond_friend_request(
    request_id: int,
    data: RespondRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.action not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="Invalid action")

    result = await db.execute(
        select(FriendRequest).where(
            FriendRequest.id == request_id,
            FriendRequest.receiver_id == current_user.id,
            FriendRequest.status == "pending",
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Friend request not found")

    if data.action == "accept":
        req.status = "accepted"
        friendship = Friendship(user1_id=min(req.sender_id, req.receiver_id), user2_id=max(req.sender_id, req.receiver_id))
        db.add(friendship)
        await db.flush()
        await manager.send_personal(req.sender_id, {
            "type": "friend_accepted",
            "user_id": current_user.id,
            "username": current_user.username,
        })
        return SuccessResponse(message="Friend request accepted")
    else:
        req.status = "rejected"
        await db.flush()
        return SuccessResponse(message="Friend request rejected")


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------

@router.get("/friends")
async def list_friends(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Friendship).where(or_(Friendship.user1_id == current_user.id, Friendship.user2_id == current_user.id))
    )
    friendships = result.scalars().all()

    items = []
    for f in friendships:
        friend_id = f.user2_id if f.user1_id == current_user.id else f.user1_id
        user_result = await db.execute(select(User).where(User.id == friend_id))
        friend = user_result.scalar_one_or_none()
        if not friend:
            continue
        profile = await _get_or_create_profile(friend.id, db)
        items.append({
            "id": friend.id,
            "username": friend.username,
            "full_name": profile.full_name,
            "bio": profile.bio,
            "profile_photo_url": profile.profile_photo_url,
            "online": manager.is_online(friend.id),
        })
    return {"items": items}


@router.delete("/friends/{friend_id}", response_model=SuccessResponse)
async def remove_friend(friend_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.user1_id == current_user.id, Friendship.user2_id == friend_id),
                and_(Friendship.user1_id == friend_id, Friendship.user2_id == current_user.id),
            )
        )
    )
    friendship = result.scalar_one_or_none()
    if not friendship:
        raise HTTPException(status_code=404, detail="Friendship not found")
    await db.delete(friendship)
    return SuccessResponse(message="Friend removed")


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@router.get("/messages/{friend_id}")
async def get_messages(friend_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not await _are_friends(current_user.id, friend_id, db):
        raise HTTPException(status_code=403, detail="You can only view messages with friends")

    result = await db.execute(
        select(Message).where(
            or_(
                and_(Message.sender_id == current_user.id, Message.receiver_id == friend_id, Message.deleted_by_sender.is_(False)),
                and_(Message.sender_id == friend_id, Message.receiver_id == current_user.id, Message.deleted_by_receiver.is_(False)),
            )
        ).order_by(Message.timestamp.asc())
    )
    messages = result.scalars().all()
    return {"items": [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "content": m.content,
            "file_url": m.file_url,
            "file_type": m.file_type,
            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            "is_read": m.is_read,
        }
        for m in messages
    ]}


@router.post("/messages/{friend_id}/read", response_model=SuccessResponse)
async def mark_messages_read(friend_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message).where(
            Message.sender_id == friend_id,
            Message.receiver_id == current_user.id,
            Message.is_read.is_(False),
        )
    )
    for m in result.scalars().all():
        m.is_read = True
    await db.flush()
    return SuccessResponse(message="Messages marked as read")


# ---------------------------------------------------------------------------
# Notifications (in-app, polling-based)
# ---------------------------------------------------------------------------

@router.get("/notifications")
async def get_notifications(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pending_result = await db.execute(
        select(func.count()).select_from(FriendRequest).where(
            FriendRequest.receiver_id == current_user.id, FriendRequest.status == "pending"
        )
    )
    pending_requests = pending_result.scalar() or 0

    unread_result = await db.execute(
        select(Message.sender_id, func.count()).where(
            Message.receiver_id == current_user.id,
            Message.is_read.is_(False),
            Message.deleted_by_receiver.is_(False),
        ).group_by(Message.sender_id)
    )
    unread_by_friend = {str(sender_id): count for sender_id, count in unread_result.all()}
    unread_messages = sum(unread_by_friend.values())

    return {
        "pending_requests": pending_requests,
        "unread_messages": unread_messages,
        "unread_by_friend": unread_by_friend,
    }


# ---------------------------------------------------------------------------
# File upload (images for chat)
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_chat_file(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    if file.content_type not in ALLOWED_CHAT_FILE_TYPES:
        raise HTTPException(status_code=400, detail="Only images are supported")
    result = await storage_service.upload_file(file, subfolder="chat", allowed_types=ALLOWED_CHAT_FILE_TYPES)
    return {"file_url": result["file_url"], "file_type": result["file_type"]}


@router.delete("/messages/{friend_id}", response_model=SuccessResponse)
async def delete_chat_history(friend_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sent_result = await db.execute(
        select(Message).where(Message.sender_id == current_user.id, Message.receiver_id == friend_id)
    )
    for m in sent_result.scalars().all():
        m.deleted_by_sender = True

    received_result = await db.execute(
        select(Message).where(Message.sender_id == friend_id, Message.receiver_id == current_user.id)
    )
    for m in received_result.scalars().all():
        m.deleted_by_receiver = True

    await db.flush()
    return SuccessResponse(message="Chat history deleted")


# ---------------------------------------------------------------------------
# WebSocket (real-time chat)
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def connect_websocket(websocket: WebSocket, token: str = Query(...)):
    user_id_str = verify_access_token(token)
    if not user_id_str:
        await websocket.close(code=1008)
        return
    user_id = int(user_id_str)

    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                receiver_id = data.get("to")
                content = data.get("content")
                file_url = data.get("file_url")
                file_type = data.get("file_type")
                if not receiver_id or (not content and not file_url):
                    continue

                async with AsyncSessionLocal() as db:
                    if not await _are_friends(user_id, receiver_id, db):
                        await websocket.send_json({"type": "error", "detail": "Not friends"})
                        continue
                    msg = Message(
                        sender_id=user_id,
                        receiver_id=receiver_id,
                        content=content,
                        file_url=file_url,
                        file_type=file_type,
                    )
                    db.add(msg)
                    await db.commit()
                    await db.refresh(msg)

                payload = {
                    "type": "message",
                    "message": {
                        "id": msg.id,
                        "sender_id": msg.sender_id,
                        "receiver_id": msg.receiver_id,
                        "content": msg.content,
                        "file_url": msg.file_url,
                        "file_type": msg.file_type,
                        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                        "is_read": msg.is_read,
                    },
                }
                await manager.send_personal(receiver_id, payload)
                await manager.send_personal(user_id, payload)

            elif msg_type == "typing":
                receiver_id = data.get("to")
                if receiver_id:
                    await manager.send_personal(receiver_id, {"type": "typing", "from": user_id})

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        manager.disconnect(user_id, websocket)
