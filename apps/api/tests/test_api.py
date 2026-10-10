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
        "reason": "균등 배정",
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


def test_assignment_pending_and_latest_memo_survive_reassignment(setup):
    c, ids, _ = setup
    lead = create(c["admin"])
    lid = lead["id"]
    assert lead["latest_memo"] is None
    assert lead["assignment_pending"] is False
    assert (
        c["admin"].post("/api/leads/assign", json={"lead_id": lid, "user_id": ids["admin"]}).status_code
        == 422
    )
    c["admin"].post("/api/leads/assign", json={"lead_id": lid, "user_id": ids["staff"]})
    assigned = c["staff"].get("/api/leads", params={"work_pending": True}).json()
    assert assigned["total"] == 1
    current = assigned["items"][0]
    assert c["staff"].get(f"/api/leads/{lid}").json()["assignment_pending"] is True
    worked = c["staff"].post(
        f"/api/leads/{lid}/activities",
        json={
            "version": current["version"],
            "activity_type": "CALL_CONNECTED",
            "status": "CALLBACK",
            "callback_at": "2030-10-01T14:00:00+09:00",
            "memo": "합성 상담 메모",
        },
    )
    assert worked.status_code == 201
    assert worked.json()["assignment_pending"] is False
    assert c["staff"].get("/api/leads", params={"work_pending": True}).json()["total"] == 0
    # A newer activity without a memo must not hide the last written memo.
    blank = c["staff"].post(
        f"/api/leads/{lid}/activities",
        json={
            "version": worked.json()["version"],
            "activity_type": "CALL_ATTEMPT",
            "memo": "   ",
        },
    )
    assert blank.status_code == 201
    assert blank.json()["latest_memo"] == "합성 상담 메모"
    c["admin"].post("/api/leads/assign", json={"lead_id": lid, "user_id": ids["other"]})
    reassigned = c["other"].get("/api/leads", params={"work_pending": True}).json()["items"][0]
    assert reassigned["assignment_pending"] is True
    assert reassigned["current_status"] == "CALLBACK"
    assert reassigned["callback_at"] == "2030-10-01T05:00:00+00:00"
    assert reassigned["latest_memo"] == "합성 상담 메모"
    assert c["staff"].get("/api/leads").json()["total"] == 0
    assert c["staff"].get(f"/api/leads/{lid}").status_code == 404
    assert (
        c["admin"]
        .post(
            f"/api/leads/{lid}/activities",
            json={
                "version": blank.json()["version"],
                "activity_type": "MEMO",
                "memo": "stale",
            },
        )
        .status_code
        == 409
    )
    # Administrator comments do not count as work by the new employee.
    added = c["admin"].post(
        f"/api/leads/{lid}/activities",
        json={
            "version": reassigned["version"],
            "activity_type": "MEMO",
            "memo": "합성 인계 메모",
        },
    )
    assert added.status_code == 201
    assert added.json()["assignment_pending"] is True


def test_admin_recovery_revokes_sessions_and_preserves_audit(setup, monkeypatch):
    from app import cli
    from app.database import UserAudit

    c, ids, factory = setup
    monkeypatch.setattr(cli, "SessionLocal", factory)
    monkeypatch.setenv("LEADFLOW_BOOTSTRAP_PASSWORD", "synthetic-new-admin-password")
    monkeypatch.setattr("sys.argv", ["cli", "reset-admin-password", "--login-id", "admin"])
    cli.main()
    assert c["admin"].get("/api/auth/me").status_code == 401
    assert (
        c["admin"]
        .post(
            "/api/auth/login",
            json={
                "login_id": "admin",
                "password": "test-password-123",
            },
        )
        .status_code
        == 401
    )
    assert (
        c["admin"]
        .post(
            "/api/auth/login",
            json={
                "login_id": "admin",
                "password": "synthetic-new-admin-password",
            },
        )
        .status_code
        == 200
    )
    assert c["staff"].get("/api/auth/me").status_code == 200
    with factory() as db:
        audit = db.scalar(select(UserAudit).where(UserAudit.user_id == ids["admin"]))
        assert "password_changed" in audit.changes
        assert "synthetic-new-admin-password" not in audit.changes
    for target in ["staff", "missing"]:
        monkeypatch.setattr("sys.argv", ["cli", "reset-admin-password", "--login-id", target])
        with pytest.raises(SystemExit):
            cli.main()


def test_bootstrap_interactive_password_confirmation(monkeypatch):
    import argparse

    from app import cli

    monkeypatch.delenv("LEADFLOW_BOOTSTRAP_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    answers = iter(["synthetic-password", "synthetic-password"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    assert cli.read_password(argparse.ArgumentParser()) == "synthetic-password"
    answers = iter(["synthetic-password", "different-password"])
    with pytest.raises(SystemExit):
        cli.read_password(argparse.ArgumentParser())


def test_account_self_service_conflict_and_session_revocation(setup):
    from app.database import UserAudit

    clients, ids, factory = setup
    staff = clients["staff"]
    version = staff.get("/api/auth/me").json()["version"]
    data = {"version": version, "current_password": "wrong", "phone": "010-0000-4321"}
    assert staff.patch("/api/auth/me", json=data).status_code == 400
    data["current_password"] = "test-password-123"
    assert staff.patch("/api/auth/me", json={**data, "role": "ADMIN"}).status_code == 422
    saved = staff.patch("/api/auth/me", json=data)
    assert saved.status_code == 200
    assert saved.json()["phone"] == data["phone"]
    assert staff.patch("/api/auth/me", json=data).status_code == 409
    another = TestClient(app)
    assert (
        another.post(
            "/api/auth/login", json={"login_id": "staff", "password": "test-password-123"}
        ).status_code
        == 200
    )
    changed = staff.patch(
        "/api/auth/me",
        json={**data, "version": saved.json()["version"], "password": "replacement-password-123"},
    )
    assert changed.status_code == 200
    assert staff.get("/api/auth/me").status_code == 401
    assert another.get("/api/auth/me").status_code == 401
    assert (
        staff.post(
            "/api/auth/login", json={"login_id": "staff", "password": "replacement-password-123"}
        ).status_code
        == 200
    )
    with factory() as db:
        audits = db.scalars(select(UserAudit).where(UserAudit.user_id == ids["staff"])).all()
        assert len(audits) == 2
        assert all("replacement-password" not in item.changes for item in audits)


def test_callback_windows_use_korean_day_and_current_assignee(setup, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from app import main
    from app.database import Lead

    clients, ids, factory = setup
    instant = datetime(2030, 10, 1, 1, tzinfo=UTC)  # 10:00 KST
    monkeypatch.setattr(main, "now", lambda: instant)
    # Sessions need to remain valid at the frozen business time.
    from app.database import Session

    with factory() as db:
        for session in db.scalars(select(Session)):
            session.expires_at = instant + timedelta(days=1)
        db.commit()
    dates = [
        "2030-09-30T14:59:00+00:00",
        "2030-09-30T15:00:00+00:00",
        "2030-10-01T14:59:00+00:00",
        "2030-10-01T15:00:00+00:00",
    ]
    lead_ids = []
    for index, value in enumerate(dates):
        customer = create(clients["admin"], suffix=f"{index:04}")
        lead_ids.append(customer["id"])
        with factory() as db:
            lead = db.get(Lead, customer["id"])
            lead.current_status = "CALLBACK"
            lead.callback_at = datetime.fromisoformat(value)
            lead.assignee_id = ids["staff"]
            db.commit()
    for window, expected in [
        ("today", lead_ids[1:3]),
        ("overdue", lead_ids[:2]),
        ("upcoming", lead_ids[3:]),
        ("all", lead_ids),
    ]:
        response = clients["staff"].get(f"/api/leads?callback_window={window}")
        assert response.status_code == 200
        assert [lead["id"] for lead in response.json()["items"]] == expected
        assert clients["other"].get(f"/api/leads?callback_window={window}").json()["total"] == 0
    assert clients["staff"].get("/api/leads?callback_window=unknown").status_code == 422
    assert (
        clients["staff"].get("/api/leads?callback_window=all&page_size=1&page=2").json()["items"][0]["id"]
        == lead_ids[1]
    )


def test_correction_preserves_original_and_enforces_scope_version(setup):
    clients, ids, factory = setup
    admin, staff = clients["admin"], clients["staff"]
    lead = create(admin)
    admin.post("/api/leads/assign", json={"lead_id": lead["id"], "user_id": ids["staff"]})
    latest = staff.get(f"/api/leads/{lead['id']}").json()
    saved = staff.post(
        f"/api/leads/{lead['id']}/activities",
        json={
            "version": latest["version"],
            "activity_type": "CALL_CONNECTED",
            "status": "COMPLETED",
            "memo": "합성 원본 상담 기록",
        },
    ).json()
    original = next(event for event in saved["timeline"] if event["kind"] == "ACTIVITY")
    path = f"/api/leads/{lead['id']}/activities/{original['id']}/corrections"
    payload = {
        "version": saved["version"],
        "kind": "CORRECTION",
        "reason": "잘못 입력",
        "memo": "합성 정정 내용",
        "status": "HOLD",
    }
    assert clients["other"].post(path, json=payload).status_code == 404
    assert staff.post(path, json={**payload, "version": 1}).status_code == 409
    assert staff.post(path, json={**payload, "reason": " "}).status_code == 422
    corrected = staff.post(path, json=payload)
    assert corrected.status_code == 201
    assert corrected.json()["current_status"] == "HOLD"
    assert original in corrected.json()["timeline"]
    assert any(original["id"] in (event.get("memo") or "") for event in corrected.json()["timeline"])
    assert staff.post(path, json=payload).status_code == 409
    cancelled = staff.post(
        path, json={**payload, "version": corrected.json()["version"], "kind": "CANCELLATION", "memo": ""}
    )
    assert cancelled.status_code == 201
    assert original in cancelled.json()["timeline"]
    with factory() as db:
        assert len(db.scalars(select(Activity).where(Activity.lead_id == lead["id"])).all()) == 3


def test_lead_registration_and_edit_validation(setup):
    clients, _, _ = setup
    admin = clients["admin"]
    lead = create(admin, name="  합성 검증 고객  ")
    assert lead["name"] == "합성 검증 고객"
    for invalid in [
        {"name": "   "},
        {"phone": "010-1234"},
        {"phone": "abc01012345678"},
        {"phone": "010123456789"},
        {"source_detail": "x" * 256},
        {"initial_memo": "x" * 10001},
    ]:
        response = admin.post(
            "/api/leads",
            json={"name": "합성 고객", "phone": "01000001234", **invalid},
        )
        assert response.status_code == 422
        response = admin.patch(f"/api/leads/{lead['id']}", json={"version": lead["version"], **invalid})
        assert response.status_code == 422
    unchanged = admin.get(f"/api/leads/{lead['id']}").json()
    assert unchanged["version"] == lead["version"]
    for phone in ["02-123-4567", "02-1234-5678", "031-123-4567", "070-1234-5678", "1588-0000"]:
        assert admin.post("/api/leads", json={"name": "합성 번호 검증", "phone": phone}).status_code == 201


def test_registration_assignment_is_atomic_and_workload_is_current(setup):
    clients, ids, factory = setup
    admin = clients["admin"]
    for target in [ids["admin"], "missing-user"]:
        response = admin.post(
            "/api/leads",
            json={
                "name": "합성 등록 실패",
                "phone": "01000008001",
                "assignee_id": target,
            },
        )
        assert response.status_code == 422
        assert admin.get("/api/leads").json()["total"] == 0
        with factory() as db:
            assert db.scalars(select(Assignment)).all() == []
    lead = create(admin, "8001", assignee_id=ids["staff"])
    assert lead["assignee_id"] == ids["staff"]
    assert lead["assignment_pending"] is True
    history = admin.get(f"/api/leads/{lead['id']}/assignments").json()
    assert len(history) == 1
    assert history[0]["assignee_name"] == "staff"
    stats = admin.get("/api/dashboard").json()["staff"]
    assert next(x for x in stats if x["id"] == ids["staff"])["pending"] == 1
    assert (
        clients["staff"]
        .post(
            f"/api/leads/{lead['id']}/activities",
            json={
                "version": lead["version"],
                "activity_type": "CALL_NO_ANSWER",
                "status": "CONTACTING",
            },
        )
        .status_code
        == 201
    )
    stats = admin.get("/api/dashboard").json()["staff"]
    assert next(x for x in stats if x["id"] == ids["staff"])["pending"] == 0
    assert admin.patch(f"/api/users/{ids['other']}", json={"status": "INACTIVE"}).status_code == 200
    assert (
        admin.post(
            "/api/leads",
            json={
                "name": "합성 이용 중지",
                "phone": "01000008002",
                "assignee_id": ids["other"],
            },
        ).status_code
        == 422
    )
    assert admin.get("/api/leads").json()["total"] == 1


def test_next_customer_preserves_filters_order_and_scope(setup):
    clients, ids, _ = setup
    admin, staff = clients["admin"], clients["staff"]
    leads = [
        create(admin, f"81{i:02d}", assignee_id=ids["staff"], acquired_at=f"2026-10-{10 + i:02d}T00:00:00Z")
        for i in range(3)
    ]
    foreign = create(admin, "8199", assignee_id=ids["other"])
    assert staff.get("/api/leads", params={"after_id": foreign["id"]}).status_code == 404
    response = staff.get(
        "/api/leads",
        params={
            "after_id": leads[2]["id"],
            "work_pending": True,
            "page_size": 1,
        },
    ).json()
    assert [x["id"] for x in response["items"]] == [leads[1]["id"]]
    staff.post(
        f"/api/leads/{leads[2]['id']}/activities",
        json={
            "version": leads[2]["version"],
            "activity_type": "MEMO",
        },
    )
    assert (
        staff.get(
            "/api/leads",
            params={
                "after_id": leads[2]["id"],
                "work_pending": True,
                "page_size": 1,
            },
        ).json()["items"][0]["id"]
        == leads[1]["id"]
    )
    assert staff.get("/api/leads", params={"after_id": leads[0]["id"]}).json()["items"] == []
    assert (
        staff.get(
            "/api/leads",
            params={
                "after_id": leads[2]["id"],
                "search": "일치하지 않는 합성 고객",
            },
        ).json()["items"]
        == []
    )
    for index, lead in enumerate(leads):
        current = staff.get(f"/api/leads/{lead['id']}").json()
        staff.post(
            f"/api/leads/{lead['id']}/activities",
            json={
                "version": current["version"],
                "activity_type": "CALL_CONNECTED",
                "status": "CALLBACK",
                "callback_at": f"2030-01-{index + 1:02d}T00:00:00Z",
            },
        )
    assert (
        staff.get(
            "/api/leads",
            params={
                "after_id": leads[0]["id"],
                "callback_window": "all",
                "page_size": 1,
            },
        ).json()["items"][0]["id"]
        == leads[1]["id"]
    )
