import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Activity, Assignment, Base, User
from app.main import app, attempts, db_session, passwords


@pytest.fixture
def setup():
    database_url = os.environ.get("LEADFLOW_TEST_DATABASE_URL")
    test_schema = None
    if database_url:
        # Each test owns a fresh schema; never drop application tables.
        engine = create_engine(database_url)
        test_schema = "test_" + uuid4().hex
        with engine.begin() as connection:
            connection.execute(CreateSchema(test_schema))
        engine = engine.execution_options(schema_translate_map={None: test_schema})
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        for login, role in [("admin", "ADMIN"), ("staff", "USER"), ("other", "USER")]:
            db.add(
                User(
                    login_id=login,
                    name=login,
                    password_hash=passwords.hash("test-password-123"),
                    role=role,
                    status="ACTIVE",
                )
            )
        db.commit()
        ids = {u.login_id: u.id for u in db.scalars(select(User))}

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[db_session] = override
    attempts.clear()
    clients = {name: TestClient(app) for name in ids}
    for name, client in clients.items():
        assert (
            client.post(
                "/api/auth/login", json={"login_id": name, "password": "test-password-123"}
            ).status_code
            == 200
        )
    yield clients, ids, factory
    app.dependency_overrides.clear()
    if test_schema:
        with engine.begin() as connection:
            connection.execute(DropSchema(test_schema, cascade=True))
    engine.dispose()


def create(client, suffix="1234", **extra):
    response = client.post("/api/leads", json={"name": "테스트 고객", "phone": "010-1234-" + suffix, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_auth_and_scope(setup):
    c, ids, factory = setup
    assert TestClient(app).get("/api/leads").status_code == 401
    assert c["staff"].get("/api/users").status_code == 403
    assert (
        c["staff"].post("/api/auth/logout", json={}, headers={"origin": "https://evil.example"}).status_code
        == 403
    )
    lead = create(c["admin"])
    assert c["staff"].get("/api/leads").json()["total"] == 0
    assert c["staff"].get(f"/api/leads/{lead['id']}").status_code == 404
    assert (
        c["admin"]
        .post("/api/leads/assign", json={"lead_id": lead["id"], "user_id": ids["staff"]})
        .status_code
        == 200
    )
    assert c["staff"].get("/api/leads").json()["total"] == 1
    assert c["other"].get(f"/api/leads/{lead['id']}/activities").status_code == 404
    c["admin"].post("/api/leads/assign", json={"lead_id": lead["id"], "user_id": ids["other"]})
    assert c["staff"].get(f"/api/leads/{lead['id']}").status_code == 404
    assert len(c["other"].get(f"/api/leads/{lead['id']}").json()["timeline"]) == 2
    with factory() as db:
        db.get(User, ids["other"]).status = "INACTIVE"
        db.commit()
    assert c["other"].get("/api/auth/me").status_code == 401
    assert c["admin"].post("/api/auth/logout", json={}).status_code == 204
    assert c["admin"].get("/api/auth/me").status_code == 401


def test_duplicates_filters_delete(setup):
    c, _, _ = setup
    admin = c["admin"]
    lead = create(admin, source="NAVER", acquired_at="2026-09-29T02:00:00Z")
    duplicate = admin.post("/api/leads", json={"name": "가족", "phone": "+82 10 1234 1234"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "DUPLICATE_PHONE"
    assert (
        admin.post(
            "/api/leads", json={"name": "가족", "phone": "01012341234", "allow_duplicate": True}
        ).status_code
        == 201
    )
    result = admin.get(
        "/api/leads",
        params={
            "search": "1234-1234",
            "source": "NAVER",
            "acquired_from": "2026-09-29",
            "acquired_to": "2026-09-29",
            "page_size": 1,
        },
    ).json()
    assert result["total"] == 1
    assert admin.delete(f"/api/leads/{lead['id']}").status_code == 204
    assert admin.get(f"/api/leads/{lead['id']}").status_code == 404


def test_activity_atomic_and_versions(setup):
    c, _, factory = setup
    admin = c["admin"]
    lead = create(admin)
    url = f"/api/leads/{lead['id']}/activities"
    body = {
        "version": lead["version"],
        "activity_type": "CALL_CONNECTED",
        "status": "CALLBACK",
        "memo": "재통화",
    }
    assert admin.post(url, json=body).status_code == 422
    with factory() as db:
        assert db.scalar(select(Activity)) is None
    good = admin.post(url, json={**body, "callback_at": "2026-10-01T14:00:00+09:00"})
    assert good.status_code == 201, good.text
    current = good.json()
    assert current["version"] == lead["version"] + 1
    assert current["callback_at"] == "2026-10-01T05:00:00+00:00"
    assert current["timeline"][0]["previous_status"] == "NEW"
    assert admin.post(url, json={**body, "status": "COMPLETED"}).status_code == 409
    done = admin.post(
        url, json={"version": current["version"], "activity_type": "CONSULTATION", "status": "COMPLETED"}
    )
    assert done.json()["callback_at"] is None
    assert len(done.json()["timeline"]) == 2


def test_bulk_atomic_balance(setup):
    c, ids, factory = setup
    leads = [create(c["admin"], f"{i:04d}") for i in range(7)]
    body = {
        "lead_ids": [x["id"] for x in leads],
        "user_ids": [ids["staff"], ids["other"]],
        "reason": "균등 배분",
    }
    assert (
        c["admin"]
        .post("/api/leads/bulk-assign", json={**body, "lead_ids": [leads[0]["id"], "missing"]})
        .status_code
        == 404
    )
    with factory() as db:
        assert db.scalar(select(Assignment)) is None
    result = c["admin"].post("/api/leads/bulk-assign", json=body)
    assert result.status_code == 200, result.text
    assert result.json()["assigned_count"] == 7
    assert c["staff"].get("/api/leads").json()["total"] == 4
    assert c["other"].get("/api/leads").json()["total"] == 3
    assert c["staff"].get("/api/dashboard").json()["total"] == 4


def test_accounts_and_patch(setup):
    c, ids, _ = setup
    admin = c["admin"]
    assert admin.patch(f"/api/users/{ids['admin']}", json={"status": "INACTIVE"}).status_code == 409
    assert admin.patch(f"/api/users/{ids['staff']}", json={"password": "new-password-123"}).status_code == 200
    assert c["staff"].get("/api/auth/me").status_code == 401
    assert (
        admin.post(
            "/api/users", json={"login_id": "newstaff", "name": "새 직원", "password": "123"}
        ).status_code
        == 422
    )
    assert (
        admin.post(
            "/api/users", json={"login_id": "newstaff", "name": "새 직원", "password": "safe-password-123"}
        ).status_code
        == 201
    )
    lead = create(admin)
    url = f"/api/leads/{lead['id']}"
    updated = admin.patch(url, json={"version": lead["version"], "name": "수정 이름"})
    assert updated.status_code == 200
    assert admin.patch(url, json={"version": lead["version"], "name": "덮어쓰기"}).status_code == 409
    assert admin.patch(url, json={"version": updated.json()["version"], "name": None}).status_code == 422


def test_duplicate_login_and_nullable_required(setup):
    c, ids, _ = setup
    admin = c["admin"]
    assert (
        admin.post(
            "/api/users", json={"login_id": "staff", "name": "중복", "password": "safe-password-123"}
        ).status_code
        == 409
    )
    assert admin.patch(f"/api/users/{ids['staff']}", json={"role": None}).status_code == 422
    assert (
        admin.post(
            "/api/leads", json={"name": "시간", "phone": "01012349999", "acquired_at": "2026-09-29T12:00:00"}
        ).status_code
        == 422
    )
    create(admin, acquired_at="2026-09-28T16:00:00Z")
    assert (
        admin.get("/api/leads", params={"acquired_from": "2026-09-29", "acquired_to": "2026-09-29"}).json()[
            "total"
        ]
        == 1
    )
    assert admin.get("/api/leads", params={"acquired_to": "2026-09-28"}).json()["total"] == 0


def test_database_concurrent_write_rolls_back_activity(setup):
    from sqlalchemy.orm.exc import StaleDataError

    from app.database import Lead

    c, _, factory = setup
    lead = create(c["admin"])
    with factory() as first, factory() as second:
        old = first.get(Lead, lead["id"])
        current = second.get(Lead, lead["id"])
        current.name = "new version"
        second.commit()
        old.name = "stale overwrite"
        first.add(
            Activity(lead_id=old.id, user_id=old.created_by, activity_type="MEMO", memo="must rollback")
        )
        with pytest.raises(StaleDataError):
            first.commit()
        first.rollback()
    with factory() as db:
        assert db.get(Lead, lead["id"]).name == "new version"
        assert db.scalar(select(Activity)) is None


def test_recent_activity_field(setup):
    c, _, _ = setup
    admin = c["admin"]
    lead = create(admin)
    assert lead["last_activity_at"] is None
    assert admin.get("/api/leads").json()["items"][0]["last_activity_at"] is None
    result = admin.post(
        f"/api/leads/{lead['id']}/activities",
        json={"version": lead["version"], "activity_type": "MEMO", "memo": "첫 활동"},
    )
    assert result.status_code == 201
    stamp = result.json()["timeline"][0]["created_at"]
    assert admin.get("/api/leads").json()["items"][0]["last_activity_at"] == stamp
    assert admin.get(f"/api/leads/{lead['id']}").json()["last_activity_at"] == stamp
