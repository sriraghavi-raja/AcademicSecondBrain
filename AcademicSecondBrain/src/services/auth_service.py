import hashlib
import os
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from src.rag.registry import auth as auth_registry


class AuthError(Exception):
    pass


class AuthorizationError(AuthError):
    pass


class AuthService:
    def __init__(self, secret_key: str | None = None, access_minutes: int = 15, refresh_days: int = 30):
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY")
        if not self.secret_key or len(self.secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        self.access_minutes = access_minutes
        self.refresh_days = refresh_days

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _password_hash(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _password_matches(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _access_token(self, user: sqlite3.Row) -> str:
        expires_at = self._now() + timedelta(minutes=self.access_minutes)
        return jwt.encode(
            {"sub": user["user_id"], "name": user["name"], "role": user["role"], "type": "access", "exp": expires_at},
            self.secret_key,
            algorithm="HS256",
        )

    def _refresh_token(self, user_id: str) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(48)
        expires_at = self._now() + timedelta(days=self.refresh_days)
        with auth_registry.get_db_connection() as connection:
            connection.execute(
                "INSERT INTO refresh_sessions VALUES (?, ?, ?, ?, ?, NULL)",
                (str(uuid4()), user_id, self._token_hash(token), self._now().isoformat(), expires_at.isoformat()),
            )
            connection.commit()
        return token, expires_at

    @staticmethod
    def _user_response(user: sqlite3.Row) -> dict[str, Any]:
        return {
            "user_id": user["user_id"],
            "name": user["name"],
            "email": user["email"],
            "college_name": user["college_name"],
            "college_year": user["college_year"],
            "role": user["role"],
            "created_at": user["created_at"],
        }

    def signup(
        self,
        name: str,
        email: str,
        password: str,
        college_name: str,
        college_year: str,
        role: str = "student",
        admin_signup_key: str | None = None,
    ) -> dict[str, Any]:
        if role not in {"student", "admin"}:
            raise AuthError("role must be student or admin")
        configured_admin_key = os.getenv("ADMIN_SIGNUP_KEY")
        if role == "admin" and (not configured_admin_key or admin_signup_key != configured_admin_key):
            raise AuthorizationError("Admin signup requires a valid server-side signup key")
        user = (
            str(uuid4()), name.strip(), email.strip().lower(), self._password_hash(password),
            college_name.strip(), college_year.strip(), role, self._now().isoformat(),
        )
        try:
            with auth_registry.get_db_connection() as connection:
                connection.execute(
                    "INSERT INTO users (user_id, name, email, password_hash, college_name, college_year, role, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    user,
                )
                connection.commit()
                created_user = connection.execute("SELECT * FROM users WHERE user_id = ?", (user[0],)).fetchone()
        except sqlite3.IntegrityError as error:
            raise AuthError("Name or email is already registered") from error
        return self._tokens(created_user)

    def login(self, name: str, password: str) -> dict[str, Any]:
        with auth_registry.get_db_connection() as connection:
            user = connection.execute("SELECT * FROM users WHERE name = ?", (name.strip(),)).fetchone()
        if user is None or not self._password_matches(password, user["password_hash"]):
            raise AuthError("Invalid name or password")
        return self._tokens(user)

    def _tokens(self, user: sqlite3.Row) -> dict[str, Any]:
        refresh_token, refresh_expires_at = self._refresh_token(user["user_id"])
        return {
            "access_token": self._access_token(user),
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_minutes * 60,
            "refresh_expires_at": refresh_expires_at.isoformat(),
            "user": self._user_response(user),
        }

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        token_hash = self._token_hash(refresh_token)
        now = self._now()
        with auth_registry.get_db_connection() as connection:
            row = connection.execute(
                "SELECT s.*, u.* FROM refresh_sessions s JOIN users u ON u.user_id = s.user_id "
                "WHERE s.token_hash = ? AND s.revoked_at IS NULL",
                (token_hash,),
            ).fetchone()
            if row is None or datetime.fromisoformat(row["expires_at"]) <= now:
                raise AuthError("Invalid or expired refresh token")
            connection.execute("UPDATE refresh_sessions SET revoked_at = ? WHERE token_hash = ?", (now.isoformat(), token_hash))
            connection.commit()
        return self._tokens(row)

    def logout(self, refresh_token: str) -> None:
        with auth_registry.get_db_connection() as connection:
            connection.execute(
                "UPDATE refresh_sessions SET revoked_at = ? WHERE token_hash = ?",
                (self._now().isoformat(), self._token_hash(refresh_token)),
            )
            connection.commit()

    def user_from_access_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            if payload.get("type") != "access" or not payload.get("sub"):
                raise AuthError("Invalid access token")
        except jwt.PyJWTError as error:
            raise AuthError("Invalid or expired access token") from error
        with auth_registry.get_db_connection() as connection:
            user = connection.execute("SELECT * FROM users WHERE user_id = ?", (payload["sub"],)).fetchone()
        if user is None:
            raise AuthError("User no longer exists")
        return self._user_response(user)

    def list_users(self) -> list[dict[str, Any]]:
        with auth_registry.get_db_connection() as connection:
            users = connection.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [self._user_response(user) for user in users]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with auth_registry.get_db_connection() as connection:
            user = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return self._user_response(user) if user else None

    def update_role(self, user_id: str, role: str) -> dict[str, Any]:
        if role not in {"student", "admin"}:
            raise AuthError("role must be student or admin")
        with auth_registry.get_db_connection() as connection:
            cursor = connection.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
            connection.commit()
            if cursor.rowcount == 0:
                raise AuthError("User not found")
            user = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return self._user_response(user)

    def delete_user(self, user_id: str) -> None:
        with auth_registry.get_db_connection() as connection:
            # SQLite does not enforce the ON DELETE CASCADE on refresh_sessions unless foreign keys are switched on
            connection.execute("DELETE FROM refresh_sessions WHERE user_id = ?", (user_id,))
            cursor = connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            connection.commit()
        if cursor.rowcount == 0:
            raise AuthError("User not found")