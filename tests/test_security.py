import json
from pathlib import Path
import tempfile
import unittest

from grid_resilience_security import (
    AuthorizationError,
    HashChainedAuditLog,
    LocalIdentityStore,
    Permission,
    Role,
    require,
)


class SecurityTests(unittest.TestCase):
    def test_rbac_accounts_and_audit_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = LocalIdentityStore(root / "identities.json")
            admin = store.bootstrap_administrator("admin.user", "Strong-Password-2026!")
            analyst = store.create_user(admin, "analyst.user", "Analyst-Password-2026!", Role.ANALYST)
            authenticated = store.authenticate("analyst.user", "Analyst-Password-2026!")
            self.assertEqual(authenticated.role, Role.ANALYST)
            require(authenticated, Permission.RUN_AC_POWER_FLOW)
            with self.assertRaises(AuthorizationError):
                require(authenticated, Permission.RUN_OPTIMIZATION)
            with self.assertRaises(AuthorizationError):
                store.create_user(authenticated, "unauthorized", "Another-Password-2026!", Role.VIEWER)
            audit = HashChainedAuditLog(root / "audit.jsonl")
            audit.append(admin, "bootstrap", "success")
            audit.append(analyst.username, "ac_power_flow", "success", "two-bus case")
            self.assertEqual(audit.verify()[0], True)
            self.assertEqual(len(audit.entries()), 2)

    def test_audit_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            audit = HashChainedAuditLog(path)
            audit.append("system", "test", "success", "original")
            record = json.loads(path.read_text(encoding="utf-8"))
            record["detail"] = "tampered"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            valid, message = audit.verify()
            self.assertFalse(valid)
            self.assertIn("Hash mismatch", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
