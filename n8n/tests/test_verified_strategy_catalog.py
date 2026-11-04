"""Regression: ONLY selected and actually verified strategy snapshots accumulate."""
from __future__ import annotations
import base64,gzip,hashlib,json,os,sys,tempfile
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/"editor-adapter"
sys.path.insert(0,str(ROOT))
import investment_verified_catalog as cat


class CatalogTests(TestCase):
 def setUp(self):
    self.temp=tempfile.TemporaryDirectory()
    self.previous=os.environ.get("STUDIO_DB_PATH")
    os.environ["STUDIO_DB_PATH"]=str(Path(self.temp.name)/"catalog.sqlite3")
    cat.initialize()
    # A real selected WF-02 source presupposes the original source store.
    # Keep candidate discovery's production missing-table fail-closed guard.
    from investment_source_registry import open_registry
    with open_registry() as db:
        db.execute("""CREATE TABLE investment_pine_payloads(
            kind TEXT,source_id TEXT,version_key TEXT,
            pine_code TEXT,rights_state TEXT)""")
        db.commit()
    fixture=Path(os.environ.get("DDDS_FIXTURE_PATH") or (Path(__file__).resolve().parents[1]/"editor-adapter"/"fixtures"/"ddds_published_source.gz.b64"))
    self.original=gzip.decompress(base64.b64decode(fixture.read_text().strip())).decode()
    self.assertEqual(hashlib.sha256(self.original.encode()).hexdigest(),cat.DDDS_SHA)
    self.assertEqual(len(self.original.splitlines()),141)
    self.ddds={"source_id":cat.DDDS_ID,"version_key":cat.DDDS_VERSION,
          "source_sha256":cat.DDDS_SHA,"rights_state":"APPROVED",
          "tradingview_original_title":"Original DDDS","free_pyne_generated_stored":True}
    self.saved={"status":"ok","count":1,"sources":[self.ddds]}
 def tearDown(self):
    if self.previous is None:os.environ.pop("STUDIO_DB_PATH",None)
    else:os.environ["STUDIO_DB_PATH"]=self.previous
    self.temp.cleanup()

 def _source(self,**patches):
    return {"pine_code":self.original,"rights_state":"APPROVED",**patches}

 def test_initial_catalog_is_empty_not_all_tradingview(self):
    self.assertEqual(cat.catalog()["items"],[])
    self.assertEqual(cat.catalog()["count"],0)

 def test_converted_only_does_not_get_published(self):
    with patch.object(cat,"_stored_source",return_value=self._source()),\
         patch.object(cat,"_stored_python",return_value="f"*64):
      candidate=cat.candidate_check(self.ddds)
      self.assertFalse(candidate["publish_ready"])
      self.assertEqual(candidate["reason"],"SAME_OHLCV_PINE_PYTHON_PARITY_NOT_VERIFIED")

 def test_source_rights_must_be_approved(self):
    candidate=cat.candidate_check({**self.ddds,"rights_state":"PENDING_REVIEW"})
    self.assertFalse(candidate["publish_ready"])
    self.assertEqual(candidate["reason"],"PINE_RIGHTS_NOT_APPROVED")

 def test_wrong_source_sha_blocks(self):
    wrong={**self.ddds,"source_sha256":"0"*64}
    with patch.object(cat,"_stored_source",return_value=self._source()):
      candidate=cat.candidate_check(wrong)
      self.assertFalse(candidate["publish_ready"])
      self.assertEqual(candidate["reason"],"PINNED_SOURCE_NOT_FOUND")

 def test_unsupported_other_strategy_cannot_steal_ddds_proof(self):
    wrong={**self.ddds,"source_id":"PUB;some-other-script"}
    with patch.object(cat,"_stored_source",return_value=self._source()),\
         patch.object(cat,"_stored_python",return_value=cat.DDDS_PY_SHA):
      result=cat.candidate_check(wrong)
      self.assertFalse(result["publish_ready"])

 def test_selected_ddds_publishes_only_once_and_survives_reopen(self):
    import investment_pipeline
    with patch.object(investment_pipeline,"saved_sources",return_value=self.saved),\
         patch.object(cat,"_stored_source",return_value=self._source()),\
         patch.object(cat,"_stored_python",return_value=cat.DDDS_PY_SHA):
      self.assertEqual(cat.candidates()["published_count"],0)
      self.assertEqual(cat.candidates()["ready_count"],1)
      first=cat.select_and_publish(cat.DDDS_ID,cat.DDDS_VERSION,cat.DDDS_SHA)
      again=cat.select_and_publish(cat.DDDS_ID,cat.DDDS_VERSION,cat.DDDS_SHA)
      self.assertEqual(first["status"],"VERIFIED_STRATEGY_PUBLISHED")
      self.assertEqual(again["status"],"VERIFIED_STRATEGY_PUBLISHED")
      self.assertEqual(cat.candidates()["published_count"],1)
    result=cat.catalog()
    self.assertEqual(result["count"],1)
    self.assertEqual(result["items"][0]["script_id_part"],cat.DDDS_ID)
    self.assertEqual(result["items"][0]["numeric_points"],864)
    self.assertEqual(result["items"][0]["numeric_mismatches"],0)
    self.assertTrue(result["published_only"])
    self.assertEqual(cat.catalog(query="decycler")["count"],1)
    self.assertEqual(cat.catalog(query="nonexistent")["count"],0)
    self.assertEqual(cat.catalog(script_type="indicators")["count"],0)
    self.assertEqual(cat.catalog(limit=1,offset=1)["items"],[])

 def test_unverified_source_does_not_write(self):
    import investment_pipeline
    with patch.object(investment_pipeline,"saved_sources",return_value=self.saved),\
         patch.object(cat,"_stored_source",return_value=self._source()),\
         patch.object(cat,"_stored_python",return_value=None):
      with self.assertRaisesRegex(ValueError,"NOT_A_SELECTED_VERIFIED_SOURCE"):
        cat.select_and_publish(cat.DDDS_ID,cat.DDDS_VERSION,cat.DDDS_SHA)
    self.assertEqual(cat.catalog()["count"],0)

 def test_invalid_selection_and_pagination_do_not_change_database(self):
    with self.assertRaisesRegex(ValueError,"EXACT_SOURCE_VERSION_SHA_REQUIRED"):
      cat.select_and_publish(cat.DDDS_ID,cat.DDDS_VERSION,"0")
    with self.assertRaisesRegex(ValueError,"INVALID_VERIFIED_CATALOG_PAGINATION"):
      cat.catalog(limit=0)
    self.assertEqual(cat.catalog()["count"],0)

if __name__=="__main__":main()
