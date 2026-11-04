"""Regression: real user DDDS must load if upstream TV source collector returns 502.

The archived 141-line user's DDDS source is exact SHA-256 and must never
masquerade as a TradingView live-chart data export or generic script source.
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import main
from pinned_ddds_source import (
    DDDS_ID,DDDS_SHA256,verified_ddds_source,pinned_ddds_source_response,
    pinned_ddds_meta_response,
)

class PinnedSourceTests(unittest.IsolatedAsyncioTestCase):
    def test_fixture_sha_is_exact_original_and_141_lines(self):
        pine=verified_ddds_source()
        self.assertEqual(hashlib.sha256(pine.encode("utf-8")).hexdigest(),DDDS_SHA256)
        self.assertEqual(len(pine.splitlines()),141)
        self.assertIn("strategy(",pine)
        self.assertIn("//@version=6",pine)

    def test_source_response_fails_closed_if_fixture_corrupt(self):
        import pinned_ddds_source as pinned
        pinned.verified_ddds_source.cache_clear()
        with patch.object(pinned.Path,"read_text",return_value="not-base64"):
            with self.assertRaises((ValueError,Exception)):
                pinned.verified_ddds_source()
        pinned.verified_ddds_source.cache_clear()
        self.assertEqual(hashlib.sha256(pinned.verified_ddds_source().encode()).hexdigest(),DDDS_SHA256)

    async def test_ddds_original_is_readable_even_when_collector_throws_502(self):
        from fastapi import HTTPException
        async def unavailable(*args,**kwargs):
            raise HTTPException(status_code=502,detail="upstream 502: /api/v1/tradingview/scripts/.../source")
        with patch.object(main,"_get",side_effect=unavailable) as called:
            result=await main.script_source(DDDS_ID)
            meta=await main.script_meta(DDDS_ID)
            called.assert_not_called()
        self.assertEqual(result["source_hash"],DDDS_SHA256)
        self.assertEqual(result["source_line_count"],141)
        self.assertEqual(result["source_provenance"],"PINNED_USER_SUPPLIED_PUBLICATION_DOM_SHA256_VERIFIED")
        self.assertEqual(result["script_id_part"],DDDS_ID)
        self.assertTrue(result["ok"])
        self.assertEqual(meta["script_id_part"],DDDS_ID)
        self.assertEqual(meta["interval"],"120")
        self.assertEqual(meta["symbol"],"BATS:AMZN")
        self.assertFalse(result["official_tradingview_chart_parity_verified"])

    async def test_other_script_keeps_original_upstream_behavior(self):
        async def unavailable(*args,**kwargs):
            from fastapi import HTTPException
            raise HTTPException(status_code=502,detail="upstream unavailable")
        with patch.object(main,"_get",side_effect=unavailable) as called:
            with self.assertRaisesRegex(Exception,"502"):
                await main.script_source("PUB;OTHER-STRATEGY")
            called.assert_awaited_once()

    async def test_real_get_routes_do_not_proxy_ddds_to_upstream(self):
        import httpx
        async def unavailable(*args,**kwargs):
            raise RuntimeError("UPSTREAM_CALLED_FOR_PINNED_DDDS")
        async with httpx.AsyncClient(
          transport=httpx.ASGITransport(app=main.app),
          base_url="http://test"
        ) as client:
            with patch.object(main,"_get",side_effect=unavailable):
                for endpoint in ("source","meta"):
                    response=await client.get("/api/public/scripts/PUB%3B5442675d418140c58486eb4a7ae12768/"+endpoint)
                    self.assertEqual(response.status_code,200,response.text[:300])
                    self.assertEqual(response.json()["script_id_part"],DDDS_ID)

if __name__=="__main__":
    unittest.main()
