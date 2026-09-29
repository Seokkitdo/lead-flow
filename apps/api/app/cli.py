"""Explicit local/demo initialization and secure administrator bootstrap."""

import argparse
import os
from datetime import timedelta

from sqlalchemy import select

from .database import Assignment, Lead, SessionLocal, User, now
from .main import passwords


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["bootstrap-admin", "seed-demo"])
    parser.add_argument("--login-id", default="admin")
    parser.add_argument("--name", default="관리자")
    args = parser.parse_args()
    password = os.environ.get("LEADFLOW_BOOTSTRAP_PASSWORD", "")
    if len(password) < 12:
        parser.error(
            "LEADFLOW_BOOTSTRAP_PASSWORD must contain at least 12 characters; no default password exists"
        )
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.login_id == args.login_id))
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
