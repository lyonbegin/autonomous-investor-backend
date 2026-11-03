"""Only contract tests. They DO NOT claim real Pine compilation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

path=Path(__file__).with_name("compile_ddds_using_free_pyne.py")
spec=importlib.util.spec_from_file_location("ddds_free_compile",path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def synthetic():
    return {"pine_source":"//@version=6\nstrategy('example')",
        "source_id":mod.SOURCE_ID,"source_sha256":mod.SOURCE_SHA,
        "source_rights":"MPL-2.0"}

class EvidenceContract(unittest.TestCase):
    def test_fake_source_never_compiles(self):
        compiler=Mock()
        with tempfile.TemporaryDirectory() as tmp:
            out=mod.compile_ddds(Path(tmp),source=synthetic(),compiler=compiler)
        self.assertEqual(out["status"],"BLOCKED_EXACT_141_LINE_SOURCE_MISMATCH")
        compiler.assert_not_called()

    def test_missing_source_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=mod.compile_ddds(Path(tmp),source={})
        self.assertEqual(out["status"],"BLOCKED_EXACT_141_LINE_SOURCE_MISMATCH")

    def test_even_compiled_never_grants_parity(self):
        out=mod.record("GENERATED_UNVALIDATED",python_sha256="e"*64)
        for field in ("python_executed","tradingview_parity_verified",
                      "pynecore_compatibility_verified","paper_enabled",
                      "live_orders_enabled"):
            self.assertIs(out[field],False)

    def test_cli_missing_reports_explicit_gate(self):
        d={"returncode":127,"reason":"PYNE_CLI_NOT_INSTALLED"}
        self.assertNotEqual(d["returncode"],0)
        self.assertEqual(mod.record("BLOCKED_PYNE_CHECK",check=d)["status"],
                         "BLOCKED_PYNE_CHECK")

if __name__=="__main__":
    unittest.main()
