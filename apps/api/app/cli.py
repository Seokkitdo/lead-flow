"""Explicit local/demo initialization and secure administrator bootstrap."""

import argparse
import getpass
import json
import os
import sys
from datetime import timedelta

from sqlalchemy import delete, select

from .database import Assignment, Lead, Session, SessionLocal, User, UserAudit, now
from .main import passwords


def read_password(parser):
    password = os.environ.get("LEADFLOW_BOOTSTRAP_PASSWORD", "")
    if not password:
        if not sys.stdin.isatty():
            parser.error("터미널에서 실행하거나 LEADFLOW_BOOTSTRAP_PASSWORD를 설정해 주세요.")
        password = getpass.getpass("새 비밀번호 (12자 이상, 입력 내용은 표시되지 않습니다): ")
        confirmation = getpass.getpass("새 비밀번호 확인: ")
        if password != confirmation:
            parser.error("비밀번호가 일치하지 않습니다. 다시 실행해 주세요.")
    if len(password) < 12:
        parser.error("비밀번호는 12자 이상이어야 합니다. 기본 비밀번호는 없습니다.")
    return password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["bootstrap-admin", "reset-admin-password", "seed-demo"])
    parser.add_argument("--login-id", default="admin")
    parser.add_argument("--name", default="관리자")
    args = parser.parse_args()
    password = read_password(parser)
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.login_id == args.login_id))
        if args.command == "reset-admin-password":
            if admin is None or admin.role != "ADMIN" or admin.status != "ACTIVE":
                parser.error("재직 중인 관리자 계정의 로그인 ID를 확인해 주세요.")
            admin.password_hash = passwords.hash(password)
            db.execute(delete(Session).where(Session.user_id == admin.id))
            db.add(
                UserAudit(
                    user_id=admin.id,
                    actor_id=admin.id,
                    changes=json.dumps({"password_changed": True, "source": "local_admin_recovery"}),
                )
            )
            db.commit()
            print(f"관리자 비밀번호 재설정 완료: {args.login_id} (기존 세션 종료)")
            return
        if admin is None:
            admin = User(
                login_id=args.login_id,
                name=args.name,
                password_hash=passwords.hash(password),
                role="ADMIN",
                status="ACTIVE",
            )
            db.add(admin)
            db.flush()
        elif args.command == "bootstrap-admin":
            parser.error("Account already exists; bootstrap never overwrites credentials")
        if args.command == "seed-demo":
            if db.scalar(select(Lead.id).limit(1)):
                parser.error("Demo seed requires an empty lead database")
            names = ["김서연", "이도윤", "박지우"]
            staff = []
            for index, name in enumerate(names):
                employee = db.scalar(select(User).where(User.login_id == f"staff{index + 1}"))
                if employee is None:
                    employee = User(
                        login_id=f"staff{index + 1}",
                        name=name,
                        password_hash=passwords.hash(password),
                        role="USER",
                        status="ACTIVE",
                    )
                    db.add(employee)
                    db.flush()
                staff.append(employee)
            customer_names = [
                "김민준",
                "이서윤",
                "박도현",
                "최하은",
                "정지호",
                "강수빈",
                "조예준",
                "윤채원",
                "장현우",
                "임다은",
                "한지민",
                "오시우",
                "서지안",
                "신유준",
                "권나연",
                "황태윤",
                "안서진",
                "송민서",
                "류하준",
                "홍예린",
                "전우진",
                "고유나",
                "문건우",
                "양서아",
            ]
            statuses = ["NEW", "CONTACTING", "CALLBACK", "IN_PROGRESS", "HOLD", "COMPLETED"]
            sources = ["NAVER", "KAKAO", "HOMEPAGE", "FORM", "PHONE", "REFERRAL"]
            for index, name in enumerate(customer_names):
                target = staff[index % 3] if index % 4 else None
                status = statuses[index % len(statuses)] if target else "NEW"
                lead = Lead(
                    name=name,
                    phone=f"010-0000-{index + 1:04d}",
                    normalized_phone=f"0100000{index + 1:04d}",
                    source=sources[index % 6],
                    initial_memo="[데모] 상담 가능 시간 확인 후 연락 요청",
                    current_status=status,
                    acquired_at=now() - timedelta(days=index // 5),
                    callback_at=now() + timedelta(hours=index) if status == "CALLBACK" else None,
                    created_by=admin.id,
                    assignee_id=target.id if target else None,
                    assigned_at=now() if target else None,
                )
                db.add(lead)
                db.flush()
                if target:
                    db.add(
                        Assignment(
                            lead_id=lead.id,
                            assignee_id=target.id,
                            assigned_by=admin.id,
                            reason="데모 초기 배분",
                        )
                    )
        db.commit()
        print(f"{args.command} completed: {args.login_id}")


if __name__ == "__main__":
    main()
