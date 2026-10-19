"""Prepare an empty production database: reference data and the first administrator.

Usage:  python -m scripts.bootstrap      (idempotent; safe to run on every start)
Env:    ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME (optional) - used only while the users table is empty

* Production stages are inserted when missing (there is no API to create them).
* Default warehouses are created only when there are no warehouses at all.
* The admin account is created only when there are no users; afterwards manage users in the UI.
"""

import os
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import StageDefinition, User, Warehouse
from app.permissions.policy import Role
from scripts.seed import STAGES

WAREHOUSES = [("RM", "Raw Material Store"), ("FG", "Finished Goods Warehouse")]


def _has_users(db) -> bool:
    return db.execute(select(User.id)).first() is not None


def main() -> None:
    db = SessionLocal()
    try:
        existing = set(db.execute(select(StageDefinition.code)).scalars())
        for code, name in STAGES:
            if code not in existing:
                db.add(StageDefinition(code=code, name=name))
        if not db.execute(select(Warehouse.id)).first():
            db.add_all([Warehouse(code=code, name=name) for code, name in WAREHOUSES])

        if not _has_users(db):
            email, password = os.environ.get("ADMIN_EMAIL", "").strip().lower(), os.environ.get("ADMIN_PASSWORD", "")
            if not email or not password:
                db.commit()
                sys.exit("No users exist: set ADMIN_EMAIL and ADMIN_PASSWORD to create the first administrator")
            if len(password) < 12:
                sys.exit("ADMIN_PASSWORD must be at least 12 characters")
            name = os.environ.get("ADMIN_NAME", "Administrator")
            db.add(User(email=email, full_name=name, role=Role.ADMIN, hashed_password=hash_password(password)))
            print(f"Created administrator {email}. Remove ADMIN_PASSWORD from the environment.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
