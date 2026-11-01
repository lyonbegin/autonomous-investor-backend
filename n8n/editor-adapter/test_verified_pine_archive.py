"""N11 pinned Pine source integrity and provenance.

Synthetic fixtures are unit tests; production N11 must re-fetch real
GitHub raw bytes and verify external corpus SHA-256 independently.
"""
import hashlib
import unittest
from unittest.mock import patch
import verified_pine_archive as archive
from investment_node_adapter import execute_node11

SYNTHETIC=("// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/\r\n"
           "// © NICK789\r\n\r\n"
           "//@version=6\r\n"
           "strategy(\"Mock for integrity-test only\", overlay=true)\r\n"
           "plot(close)\r\n").encode("utf-8")

class Response:
    status=200
    def __init__(self,raw):self.raw=raw
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,count):return self.raw[:count]

def candidate(digest):
    return {"kind":"strategy","source_id":archive.SOURCE_ID,"source_url":archive.TRADINGVIEW_URL,
            "pine_version":"6","source_license_reported":"MPL-2.0",
            "source_sha256_reported":digest}

class PinnedSource(unittest.TestCase):
    def test_accept_byte_equal_pine_from_pinned_mirror_and_preserve_notice(self):
        digest=hashlib.sha256(SYNTHETIC).hexdigest()
        with patch.object(archive,"EXPECTED_SHA256",digest),patch.object(
            archive.urllib.request,"urlopen",return_value=Response(SYNTHETIC)) as mocked:
            parent={"kind":"strategy","has_candidate":True,
                    "candidate":candidate(digest),"source_registry_checked":True}
            out=execute_node11(parent,workflow_kind="strategy")
            self.assertEqual(out["pine_source_sha256"],digest)
            self.assertTrue(out["source_hash_verified"])
            self.assertTrue(out["pine_source_acquired"])
            self.assertIn("© NICK789",out["pine_code"])
            self.assertEqual(out["pine_source_origin"],"GITHUB_PINNED_OPEN_SOURCE_ARCHIVE")
            self.assertEqual(out["rights_state"],"MPL_2_0_REVIEW_REQUIRED")
            self.assertFalse(out["tradingview_requested"])
            self.assertEqual(mocked.call_args.args[0].full_url,archive.ARCHIVE_URL)
            self.assertEqual(parent["candidate"],out["candidate"])

    def test_newline_only_canonicalization_requires_exact_sha(self):
        digest=hashlib.sha256(SYNTHETIC).hexdigest()
        mirror=SYNTHETIC.replace(b"\r\n",b"\r\r\n")
        self.assertNotEqual(hashlib.sha256(mirror).hexdigest(),digest)
        with patch.object(archive,"EXPECTED_SHA256",digest),patch.object(
            archive.urllib.request,"urlopen",return_value=Response(mirror)):
            result=archive.acquire_verified_pine(candidate(digest))
            self.assertEqual(result["pine_source_sha256"],digest)
            self.assertEqual(result["source_archive_newline_normalization"],"CRCRLF_TO_CRLF")
            self.assertEqual(result["source_archive_raw_sha256"],
                             hashlib.sha256(mirror).hexdigest())
            self.assertEqual(result["pine_code"].encode(),SYNTHETIC)

    def test_missing_author_notice_is_flagged_without_editing_original_bytes(self):
        without_notice=SYNTHETIC.replace("// © NICK789\r\n".encode("utf-8"),b"")
        sha=hashlib.sha256(without_notice).hexdigest()
        with patch("verified_pine_archive.urllib.request.urlopen",
                   return_value=Response(without_notice)):
            result=archive.acquire_verified_pine(candidate(sha))
            self.assertFalse(result["source_author_notice_present"])
            self.assertEqual(result["source_author_notice_status"],
                             "NOT_PRESENT_REVIEW_REQUIRED")
            self.assertEqual(result["pine_code"].encode("utf-8"),without_notice)
            self.assertEqual(result["rights_state"],"MPL_2_0_REVIEW_REQUIRED")

    def test_reject_modified_bytes_even_with_correct_metadata(self):
        digest=hashlib.sha256(SYNTHETIC).hexdigest()
        with patch.object(archive,"EXPECTED_SHA256",digest),patch.object(
                archive.urllib.request,"urlopen",return_value=Response(SYNTHETIC+b"modified")):
            with self.assertRaisesRegex(ValueError,"ARCHIVE_BYTES_SHA256_MISMATCH"):
                archive.acquire_verified_pine(candidate(digest))

    def test_reject_other_pine_version_and_untrusted_identity(self):
        digest=hashlib.sha256(SYNTHETIC).hexdigest()
        with patch.object(archive,"EXPECTED_SHA256",digest):
            with self.assertRaisesRegex(ValueError,"N11_NOT_IN_VERIFIED_SOURCE_ARCHIVE"):
                archive.acquire_verified_pine({**candidate(digest),"source_url":"https://www.tradingview.com/script/FAKE1234/"})
            with self.assertRaisesRegex(ValueError,"ARCHIVE_PINE_VERSION_MISMATCH"):
                archive.acquire_verified_pine({**candidate(digest),"pine_version":"4"})
            with self.assertRaisesRegex(ValueError,"ARCHIVE_LICENSE_NOT_MATCHING_CORPUS"):
                archive.acquire_verified_pine({**candidate(digest),"source_license_reported":"none"})

if __name__=="__main__":unittest.main()
