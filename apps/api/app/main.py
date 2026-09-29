# ruff: noqa: B008 -- FastAPI dependencies are declarative parameter defaults.
import hashlib
import json
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, date, datetime, timedelta, timezone
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pwdlib import PasswordHash
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm.exc import StaleDataError

from .database import Activity, Assignment, Lead, Session, SessionLocal, User, UserAudit, now, settings
from .schemas import (
    ActivityCreate,
    BulkAssign,
    LeadCreate,
    LeadPatch,
    Login,
    SingleAssign,
    StatusCreate,
    UserCreate,
    UserPatch,
)

app = FastAPI(
    title="LeadFlow API",
    version="0.1.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
)
origins = [s.strip() for s in settings.allowed_origins.split(",") if s.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)
passwords = PasswordHash.recommended()
dummy_hash = passwords.hash(secrets.token_urlsafe(32))
attempts = defaultdict(deque)
attempt_lock = Lock()


@app.middleware("http")
async def security(request: Request, call_next):
    if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
        origin = request.headers.get("origin")
        # JSON plus exact origin validation prevents cross-site cookie submissions.
        if origin and origin not in origins:
            return Response(
                content='{"detail":"Untrusted origin"}', status_code=403, media_type="application/json"
            )
        if request.headers.get("sec-fetch-site") == "cross-site" and not origin:
            return Response(status_code=403)
        if request.method != "DELETE" and not request.headers.get("content-type", "").startswith(
            "application/json"
        ):
            return Response(
                content='{"detail":"JSON required"}', status_code=415, media_type="application/json"
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def db_session():
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise


def commit(db):
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, "고객 정보가 변경되었습니다. 새로고침 후 다시 시도해 주세요.")
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "이미 사용 중인 값입니다.")


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def utc(value):
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)) if value else None


def current_user(request: Request, db: DBSession = Depends(db_session)):
    token = request.cookies.get(settings.cookie_name)
    session = db.get(Session, digest(token)) if token else None
    if not session or utc(session.expires_at) <= now():
        raise HTTPException(401, "로그인이 필요합니다.")
    user = db.get(User, session.user_id)
    if not user or user.status != "ACTIVE":
        raise HTTPException(401, "사용할 수 없는 계정입니다.")
    return user


def admin(user=Depends(current_user)):
    if user.role != "ADMIN":
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return user


def user_json(user):
    return {
        k: utc(getattr(user, k)) if k == "created_at" else getattr(user, k)
        for k in ["id", "login_id", "name", "phone", "role", "status", "created_at"]
    }


def lead_json(lead, db, activity_times=None, assignees=None):
    result = {
        k: utc(getattr(lead, k)) if k.endswith("_at") else getattr(lead, k)
        for k in [
            "id",
            "name",
            "phone",
            "source",
            "source_detail",
            "initial_memo",
            "current_status",
            "assignee_id",
            "assigned_at",
            "callback_at",
            "acquired_at",
            "created_at",
            "updated_at",
            "version",
        ]
    }
    assignee = (
        (assignees.get(lead.assignee_id) if assignees is not None else db.get(User, lead.assignee_id))
        if lead.assignee_id
        else None
    )
    result["assignee_name"] = assignee.name if assignee else None
    latest = (
        activity_times.get(lead.id)
        if activity_times is not None
        else db.scalar(select(func.max(Activity.created_at)).where(Activity.lead_id == lead.id))
    )
    result["last_activity_at"] = utc(latest)
    return result


def scoped(user):
    query = select(Lead).where(Lead.deleted_at.is_(None))
    return query if user.role == "ADMIN" else query.where(Lead.assignee_id == user.id)


def get_lead(lead_id, user, db):
    lead = db.scalar(scoped(user).where(Lead.id == lead_id))
    if lead is None:
        raise HTTPException(404, "고객을 찾을 수 없습니다.")
    return lead


def guard_version(lead, version):
    if lead.version != version:
        raise HTTPException(409, "고객 정보가 변경되었습니다. 새로고침 후 다시 시도해 주세요.")


def normalize(phone):
    value = re.sub(r"\D", "", phone)
    if value.startswith("82"):
        value = "0" + value[2:]
    if not 7 <= len(value) <= 15:
        raise HTTPException(422, "올바른 전화번호를 입력해 주세요.")
    return value


def duplicates(phone, allow, db, exclude=None):
    query = select(Lead).where(Lead.normalized_phone == phone, Lead.deleted_at.is_(None))
    if exclude:
        query = query.where(Lead.id != exclude)
    matches = db.scalars(query.limit(20)).all()
    if matches and not allow:
        # FastAPI HTTPException detail must already be JSON serializable.
        from fastapi.encoders import jsonable_encoder

        raise HTTPException(
            409, jsonable_encoder({"code": "DUPLICATE_PHONE", "matches": [lead_json(x, db) for x in matches]})
        )


@app.get("/api/health")
def health(db: DBSession = Depends(db_session)):
    db.execute(select(1))
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response, db: DBSession = Depends(db_session)):
    key = (request.client.host if request.client else "unknown", body.login_id)
    with attempt_lock:
        bucket = attempts[key]
        while bucket and bucket[0] < time.monotonic() - 300:
            bucket.popleft()
        if len(bucket) >= 10:
            raise HTTPException(429, "잠시 후 다시 로그인해 주세요.")
        bucket.append(time.monotonic())
    user = db.scalar(select(User).where(User.login_id == body.login_id))
    valid = passwords.verify(body.password, user.password_hash if user else dummy_hash)
    if not user or not valid or user.status != "ACTIVE":
        raise HTTPException(401, "아이디 또는 비밀번호를 확인해 주세요.")
    old_token = request.cookies.get(settings.cookie_name)
    old = db.get(Session, digest(old_token)) if old_token else None
    if old:
        db.delete(old)
    db.execute(delete(Session).where(Session.expires_at <= now()))
    token = secrets.token_urlsafe(48)
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=now() + timedelta(hours=settings.session_hours),
        )
    )
    commit(db)
    response.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/api",
    )
    with attempt_lock:
        attempts.pop(key, None)
    return user_json(user)


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: DBSession = Depends(db_session)):
    token = request.cookies.get(settings.cookie_name)
    session = db.get(Session, digest(token)) if token else None
    if session:
        db.delete(session)
        commit(db)
    response.delete_cookie(settings.cookie_name, path="/api")


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user_json(user)


@app.get("/api/users")
def users(user=Depends(admin), db: DBSession = Depends(db_session)):
    return [user_json(u) for u in db.scalars(select(User).order_by(User.created_at))]


@app.post("/api/users", status_code=201)
def create_user(body: UserCreate, actor=Depends(admin), db: DBSession = Depends(db_session)):
    data = body.model_dump(exclude={"password"})
    user = User(**data, password_hash=passwords.hash(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "이미 사용 중인 로그인 ID입니다.")
    db.add(
        UserAudit(
            user_id=user.id, actor_id=actor.id, changes=json.dumps({"created": data}, ensure_ascii=False)
        )
    )
    commit(db)
    return user_json(user)


@app.patch("/api/users/{user_id}")
def patch_user(user_id: str, body: UserPatch, actor=Depends(admin), db: DBSession = Depends(db_session)):
    user = db.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if not user:
        raise HTTPException(404, "직원을 찾을 수 없습니다.")
    data = body.model_dump(exclude_unset=True)
    if any(data.get(k) is None for k in ["name", "role", "status", "password"] if k in data):
        raise HTTPException(422, "필수 값은 비울 수 없습니다.")
    if actor.id == user_id and (
        data.get("role", "ADMIN") != "ADMIN" or data.get("status", "ACTIVE") != "ACTIVE"
    ):
        raise HTTPException(409, "현재 로그인한 관리자는 비활성화하거나 강등할 수 없습니다.")
    audit = {}
    for key, value in data.items():
        if key == "password":
            user.password_hash = passwords.hash(value)
            audit["password_changed"] = True
        else:
            audit[key] = {"before": getattr(user, key), "after": value}
            setattr(user, key, value)
    if "password" in data or data.get("status") in {"INACTIVE", "DEPARTED"}:
        for session in db.scalars(select(Session).where(Session.user_id == user.id)):
            db.delete(session)
    db.add(UserAudit(user_id=user.id, actor_id=actor.id, changes=json.dumps(audit, ensure_ascii=False)))
    commit(db)
    return user_json(user)


@app.get("/api/leads")
def leads(
    search: str | None = None,
    status: str | None = None,
    source: str | None = None,
    assignee_id: str | None = None,
    assignment: str | None = None,
    acquired_from: date | None = None,
    acquired_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(db_session),
):
    query = scoped(user)
    if search:
        escaped = search.replace("%", "\\%").replace("_", "\\_")
        terms = [Lead.name.ilike(f"%{escaped}%", escape="\\"), Lead.phone.ilike(f"%{escaped}%", escape="\\")]
        digits = re.sub(r"\D", "", search)
        if digits:
            terms.append(Lead.normalized_phone.contains(digits))
        query = query.where(or_(*terms))
    if status:
        query = query.where(Lead.current_status == status)
    if source:
        query = query.where(Lead.source == source)
    if assignee_id:
        query = query.where(Lead.assignee_id == assignee_id)
    if assignment == "unassigned":
        query = query.where(Lead.assignee_id.is_(None))
    elif assignment == "assigned":
        query = query.where(Lead.assignee_id.is_not(None))
    if acquired_from:
        query = query.where(
            Lead.acquired_at
            >= datetime.combine(
                acquired_from, datetime.min.time(), tzinfo=timezone(timedelta(hours=9))
            ).astimezone(UTC)
        )
    if acquired_to:
        query = query.where(
            Lead.acquired_at
            < datetime.combine(
                acquired_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone(timedelta(hours=9))
            ).astimezone(UTC)
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(Lead.acquired_at.desc(), Lead.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    activity_times = dict(
        db.execute(
            select(Activity.lead_id, func.max(Activity.created_at))
            .where(Activity.lead_id.in_([lead.id for lead in items]))
            .group_by(Activity.lead_id)
        ).all()
    )
    assignees = {
        employee.id: employee
        for employee in db.scalars(
            select(User).where(User.id.in_({lead.assignee_id for lead in items if lead.assignee_id}))
        )
    }
    return {
        "items": [lead_json(x, db, activity_times, assignees) for x in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.post("/api/leads", status_code=201)
def create_lead(body: LeadCreate, user=Depends(admin), db: DBSession = Depends(db_session)):
    normalized = normalize(body.phone)
    duplicates(normalized, body.allow_duplicate, db)
    data = body.model_dump(exclude={"allow_duplicate"}, exclude_none=True)
    lead = Lead(**data, normalized_phone=normalized, created_by=user.id)
    db.add(lead)
    commit(db)
    return lead_json(lead, db)


def assign_many(body, actor, db):
    lead_ids = list(dict.fromkeys(body.lead_ids))
    user_ids = list(dict.fromkeys(body.user_ids))
    target_map = {
        employee.id: employee
        for employee in db.scalars(
            select(User)
            .where(User.id.in_(user_ids))
            .order_by(User.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    targets = [target_map.get(uid) for uid in user_ids]
    if any(u is None or u.status != "ACTIVE" for u in targets):
        raise HTTPException(422, "활성 직원에게만 배분할 수 있습니다.")
    # Stable lock ordering avoids deadlocks for overlapping bulk assignments.
    lead_map = {
        lead.id: lead
        for lead in db.scalars(
            select(Lead)
            .where(Lead.id.in_(lead_ids), Lead.deleted_at.is_(None))
            .order_by(Lead.id)
            .with_for_update()
        )
    }
    if len(lead_map) != len(lead_ids):
        raise HTTPException(404, "일부 고객을 찾을 수 없습니다.")
    for index, lid in enumerate(lead_ids):
        lead = lead_map[lid]
        target = targets[index % len(targets)]
        db.add(
            Assignment(
                lead_id=lead.id,
                previous_assignee_id=lead.assignee_id,
                assignee_id=target.id,
                assigned_by=actor.id,
                reason=body.reason,
            )
        )
        lead.assignee_id = target.id
        lead.assigned_at = now()
        lead.updated_at = now()
    commit(db)
    return {"assigned_count": len(lead_ids), "items": [lead_json(lead_map[lid], db) for lid in lead_ids]}


@app.post("/api/leads/bulk-assign")
def bulk_assign(body: BulkAssign, user=Depends(admin), db: DBSession = Depends(db_session)):
    return assign_many(body, user, db)


@app.post("/api/leads/assign")
def single_assign(body: SingleAssign, user=Depends(admin), db: DBSession = Depends(db_session)):
    return assign_many(
        BulkAssign(lead_ids=[body.lead_id], user_ids=[body.user_id], reason=body.reason), user, db
    )


def timeline(lead_id, db):
    result = []
    for a in db.scalars(select(Activity).where(Activity.lead_id == lead_id)):
        result.append(
            {
                "id": a.id,
                "kind": "ACTIVITY",
                "created_at": utc(a.created_at),
                "actor_name": db.get(User, a.user_id).name,
                "activity_type": a.activity_type,
                "memo": a.memo,
                "previous_status": a.previous_status,
                "new_status": a.new_status,
                "callback_at": utc(a.callback_at),
            }
        )
    for a in db.scalars(select(Assignment).where(Assignment.lead_id == lead_id)):
        result.append(
            {
                "id": a.id,
                "kind": "ASSIGNMENT",
                "created_at": utc(a.created_at),
                "actor_name": db.get(User, a.assigned_by).name,
                "previous_assignee_id": a.previous_assignee_id,
                "assignee_id": a.assignee_id,
                "assignee_name": db.get(User, a.assignee_id).name,
                "reason": a.reason,
            }
        )
    return sorted(result, key=lambda x: (x["created_at"], x["id"]), reverse=True)


@app.get("/api/leads/{lead_id}")
def detail(lead_id: str, user=Depends(current_user), db: DBSession = Depends(db_session)):
    lead = get_lead(lead_id, user, db)
    return {**lead_json(lead, db), "timeline": timeline(lead.id, db)}


@app.patch("/api/leads/{lead_id}")
def patch_lead(lead_id: str, body: LeadPatch, user=Depends(admin), db: DBSession = Depends(db_session)):
    lead = get_lead(lead_id, user, db)
    guard_version(lead, body.version)
    data = body.model_dump(exclude_unset=True, exclude={"version", "allow_duplicate"})
    if any(data.get(k) is None for k in ["name", "phone", "acquired_at"] if k in data):
        raise HTTPException(422, "필수 값은 비울 수 없습니다.")
    if "phone" in data:
        normalized = normalize(data["phone"])
        duplicates(normalized, body.allow_duplicate, db, lead.id)
        lead.normalized_phone = normalized
    for key, value in data.items():
        setattr(lead, key, value)
    lead.updated_at = now()
    commit(db)
    return lead_json(lead, db)


@app.delete("/api/leads/{lead_id}", status_code=204)
def delete_lead(lead_id: str, user=Depends(admin), db: DBSession = Depends(db_session)):
    lead = get_lead(lead_id, user, db)
    lead.deleted_at = now()
    lead.updated_at = now()
    commit(db)


def add_activity(lead_id, body, user, db):
    lead = get_lead(lead_id, user, db)
    guard_version(lead, body.version)
    status = body.status or lead.current_status
    callback = body.callback_at if body.callback_at is not None else lead.callback_at
    if status == "CALLBACK" and callback is None:
        raise HTTPException(422, "재통화 일시가 필요합니다.")
    if body.callback_at and status != "CALLBACK":
        raise HTTPException(422, "재통화 예정 상태에서 일시를 입력해 주세요.")
    activity = Activity(
        lead_id=lead.id,
        user_id=user.id,
        activity_type=body.activity_type,
        memo=body.memo,
        previous_status=lead.current_status if body.status else None,
        new_status=body.status,
        callback_at=callback if status == "CALLBACK" else None,
    )
    db.add(activity)
    lead.current_status = status
    lead.callback_at = callback if status == "CALLBACK" else None
    lead.updated_at = now()
    commit(db)
    return {**lead_json(lead, db), "timeline": timeline(lead.id, db)}


@app.post("/api/leads/{lead_id}/activities", status_code=201)
def create_activity(
    lead_id: str, body: ActivityCreate, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    return add_activity(lead_id, body, user, db)


@app.post("/api/leads/{lead_id}/status", status_code=201)
def change_status(
    lead_id: str, body: StatusCreate, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    return add_activity(lead_id, ActivityCreate(**body.model_dump(), activity_type="STATUS_CHANGE"), user, db)


@app.get("/api/leads/{lead_id}/activities")
def activities(lead_id: str, user=Depends(current_user), db: DBSession = Depends(db_session)):
    get_lead(lead_id, user, db)
    return [x for x in timeline(lead_id, db) if x["kind"] == "ACTIVITY"]


@app.get("/api/leads/{lead_id}/assignments")
def assignments(lead_id: str, user=Depends(current_user), db: DBSession = Depends(db_session)):
    get_lead(lead_id, user, db)
    return [x for x in timeline(lead_id, db) if x["kind"] == "ASSIGNMENT"]


@app.get("/api/dashboard")
def dashboard(user=Depends(current_user), db: DBSession = Depends(db_session)):
    rows = db.scalars(scoped(user)).all()
    # Operational day uses Asia/Seoul; stored timestamps remain UTC.
    today = now().astimezone(timezone(timedelta(hours=9))).date()
    counts = {
        status: sum(x.current_status == status for x in rows)
        for status in ["NEW", "CONTACTING", "CALLBACK", "IN_PROGRESS", "HOLD", "REJECTED", "COMPLETED"]
    }
    staff = []
    if user.role == "ADMIN":
        for employee in db.scalars(select(User).order_by(User.name)):
            assigned = [x for x in rows if x.assignee_id == employee.id]
            staff.append(
                {
                    "id": employee.id,
                    "name": employee.name,
                    "total": len(assigned),
                    "completed": sum(x.current_status == "COMPLETED" for x in assigned),
                    "callback": sum(x.current_status == "CALLBACK" for x in assigned),
                }
            )
    return {
        "total": len(rows),
        "today_new": sum(
            utc(x.acquired_at).astimezone(timezone(timedelta(hours=9))).date() == today for x in rows
        ),
        "unassigned": sum(x.assignee_id is None for x in rows),
        "in_progress": counts["CONTACTING"] + counts["IN_PROGRESS"],
        "callback": counts["CALLBACK"],
        "completed": counts["COMPLETED"],
        "status_counts": counts,
        "staff": staff,
    }
