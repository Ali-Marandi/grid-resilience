"""Local enterprise security controls for Grid Resilience Studio.

The implementation provides RBAC, PBKDF2 password records and hash-chained audit
entries.  It protects application actions and local project governance; it does not
replace OS account controls, enterprise identity providers, HSMs or key management.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile
from typing import Any


UTC = timezone.utc
SECURITY_SCHEMA = "grid-resilience/rbac/1"
PBKDF2_ITERATIONS = 600_000


class AuthorizationError(PermissionError):
    """Raised when an authenticated identity lacks a required permission."""


class Role(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    OPERATOR = "operator"
    ADMINISTRATOR = "administrator"


class Permission(str, Enum):
    VIEW_PROJECT = "view_project"
    IMPORT_NETWORK = "import_network"
    EDIT_PROJECT = "edit_project"
    RUN_SCREENING = "run_screening"
    RUN_AC_POWER_FLOW = "run_ac_power_flow"
    RUN_OPTIMIZATION = "run_optimization"
    EXPORT_RESULTS = "export_results"
    VIEW_AUDIT = "view_audit"
    MANAGE_USERS = "manage_users"
    MANAGE_SECURITY = "manage_security"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({Permission.VIEW_PROJECT, Permission.VIEW_AUDIT}),
    Role.ANALYST: frozenset({
        Permission.VIEW_PROJECT, Permission.IMPORT_NETWORK, Permission.EDIT_PROJECT,
        Permission.RUN_SCREENING, Permission.RUN_AC_POWER_FLOW, Permission.EXPORT_RESULTS,
        Permission.VIEW_AUDIT,
    }),
    Role.OPERATOR: frozenset({
        Permission.VIEW_PROJECT, Permission.IMPORT_NETWORK, Permission.EDIT_PROJECT,
        Permission.RUN_SCREENING, Permission.RUN_AC_POWER_FLOW, Permission.RUN_OPTIMIZATION,
        Permission.EXPORT_RESULTS, Permission.VIEW_AUDIT,
    }),
    Role.ADMINISTRATOR: frozenset(Permission),
}


@dataclass(frozen=True)
class UserAccount:
    username: str
    role: Role
    password_salt_b64: str
    password_hash_b64: str
    active: bool = True
    created_at: str = ""

    def public(self) -> dict[str, Any]:
        return {"username": self.username, "role": self.role.value, "active": self.active, "created_at": self.created_at}


@dataclass(frozen=True)
class Principal:
    username: str
    role: Role


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    actor: str
    action: str
    outcome: str
    detail: str
    previous_hash: str
    entry_hash: str

    def payload(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp, "actor": self.actor, "action": self.action,
            "outcome": self.outcome, "detail": self.detail, "previous_hash": self.previous_hash,
        }


class LocalIdentityStore:
    """Atomic JSON identity store with PBKDF2-HMAC-SHA256 password records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def bootstrap_administrator(self, username: str, password: str) -> Principal:
        if self.exists():
            raise ValueError("Identity store already exists; bootstrap is allowed only once")
        account = self._new_account(username, password, Role.ADMINISTRATOR)
        self._save([account])
        return Principal(account.username, account.role)

    def authenticate(self, username: str, password: str) -> Principal:
        accounts = self._load()
        account = next((item for item in accounts if item.username.casefold() == username.strip().casefold()), None)
        if account is None or not account.active:
            # Deliberately perform comparable work for absent users to reduce trivial timing leakage.
            hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"grid-resilience-placeholder", PBKDF2_ITERATIONS)
            raise AuthorizationError("Invalid credentials or inactive account")
        expected = base64.b64decode(account.password_hash_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(account.password_salt_b64), PBKDF2_ITERATIONS)
        if not hmac.compare_digest(expected, actual):
            raise AuthorizationError("Invalid credentials or inactive account")
        return Principal(account.username, account.role)

    def create_user(self, actor: Principal, username: str, password: str, role: Role) -> UserAccount:
        require(actor, Permission.MANAGE_USERS)
        accounts = self._load()
        normalized = self._validate_username(username)
        if any(item.username.casefold() == normalized.casefold() for item in accounts):
            raise ValueError("Username already exists")
        account = self._new_account(normalized, password, role)
        accounts.append(account)
        self._save(accounts)
        return account

    def set_active(self, actor: Principal, username: str, active: bool) -> None:
        require(actor, Permission.MANAGE_USERS)
        accounts = self._load()
        target = username.strip().casefold()
        changed = False
        updated: list[UserAccount] = []
        for account in accounts:
            if account.username.casefold() == target:
                if account.role is Role.ADMINISTRATOR and not active and sum(item.active and item.role is Role.ADMINISTRATOR for item in accounts) <= 1:
                    raise ValueError("At least one active administrator must remain")
                updated.append(UserAccount(account.username, account.role, account.password_salt_b64, account.password_hash_b64, active, account.created_at))
                changed = True
            else:
                updated.append(account)
        if not changed:
            raise ValueError("Unknown username")
        self._save(updated)

    def list_users(self, actor: Principal) -> list[dict[str, Any]]:
        require(actor, Permission.MANAGE_USERS)
        return [account.public() for account in self._load()]

    def _new_account(self, username: str, password: str, role: Role) -> UserAccount:
        normalized = self._validate_username(username)
        self._validate_password(password)
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return UserAccount(
            username=normalized, role=role,
            password_salt_b64=base64.b64encode(salt).decode("ascii"),
            password_hash_b64=base64.b64encode(digest).decode("ascii"),
            created_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _validate_username(username: str) -> str:
        normalized = username.strip()
        if not 3 <= len(normalized) <= 64 or not all(char.isalnum() or char in {".", "_", "-"} for char in normalized):
            raise ValueError("Username must contain 3–64 letters, digits, dots, underscores or hyphens")
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 12:
            raise ValueError("Password must contain at least 12 characters")
        kinds = sum(bool(any(test(char) for char in password)) for test in (str.islower, str.isupper, str.isdigit, lambda value: not value.isalnum()))
        if kinds < 3:
            raise ValueError("Password must use at least three character classes")

    def _load(self) -> list[UserAccount]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError("Identity store has not been initialized")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Identity store is invalid JSON: {exc}") from exc
        if raw.get("schema") != SECURITY_SCHEMA:
            raise ValueError("Unsupported identity-store schema")
        try:
            return [UserAccount(username=item["username"], role=Role(item["role"]), password_salt_b64=item["password_salt_b64"], password_hash_b64=item["password_hash_b64"], active=bool(item.get("active", True)), created_at=item.get("created_at", "")) for item in raw["users"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Identity store record is invalid: {exc}") from exc

    def _save(self, accounts: list[UserAccount]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": SECURITY_SCHEMA, "password_kdf": "PBKDF2-HMAC-SHA256", "iterations": PBKDF2_ITERATIONS, "users": [asdict(account) | {"role": account.role.value} for account in accounts]}
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent, suffix=".tmp") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass


def require(principal: Principal, permission: Permission) -> None:
    if permission not in ROLE_PERMISSIONS[principal.role]:
        raise AuthorizationError(f"{principal.role.value} role does not permit {permission.value}")


class HashChainedAuditLog:
    """Append-only JSONL audit evidence with deterministic hash-chain verification."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, actor: Principal | str, action: str, outcome: str, detail: str = "") -> AuditEntry:
        previous = self._last_hash()
        payload = {
            "timestamp": datetime.now(UTC).isoformat(), "actor": actor.username if isinstance(actor, Principal) else str(actor),
            "action": action, "outcome": outcome, "detail": detail, "previous_hash": previous,
        }
        digest = self._hash(payload)
        entry = AuditEntry(**payload, entry_hash=digest)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        return entry

    def verify(self) -> tuple[bool, str]:
        if not self.path.exists():
            return True, "No audit file exists yet"
        previous = ""
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                raw = json.loads(line)
                entry = AuditEntry(**raw)
            except (json.JSONDecodeError, TypeError) as exc:
                return False, f"Malformed audit entry on line {line_number}: {exc}"
            if entry.previous_hash != previous:
                return False, f"Broken hash chain on line {line_number}"
            if not hmac.compare_digest(entry.entry_hash, self._hash(entry.payload())):
                return False, f"Hash mismatch on line {line_number}"
            previous = entry.entry_hash
        return True, f"Verified {len(self.path.read_text(encoding='utf-8').splitlines())} audit entries"

    def entries(self, limit: int = 100) -> list[AuditEntry]:
        if not self.path.exists():
            return []
        records: list[AuditEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines()[-limit:]:
            records.append(AuditEntry(**json.loads(line)))
        return records

    def _last_hash(self) -> str:
        if not self.path.exists():
            return ""
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])["entry_hash"] if lines else ""

    @staticmethod
    def _hash(payload: dict[str, str]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
