"""Static contract checks for the independently packaged market home."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = ROOT / "admin-console" / "markets.html"
DOCKER = ROOT / "Dockerfile.native-editor-gateway"

class MarketPageContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        cls.docker = DOCKER.read_text(encoding="utf-8")

    def test_ten_market_sections(self):
        for key in ("indices", "kr", "world", "crypto", "futures", "forex", "bonds", "corporate", "etf", "economy"):
            self.assertIn('id:"'+key+'"', self.html)

    def test_real_controls_and_missing_data_label(self):
        for item in ("data-select=", "data-period=", "data-item=", "mountChart(", "openDetail(", "시세 미연결", "시세 데이터"):
            self.assertIn(item, self.html)

    def test_no_fake_quotes(self):
        self.assertNotIn("Math.random", self.html)
        self.assertNotIn("mockPrice", self.html)
        self.assertIn("실시간·지연 정보는 아직 연결되지 않았습니다", self.html)

    def test_packaged_into_existing_service(self):
        self.assertIn("COPY n8n/admin-console/markets.html /app/dist/admin/markets.html", self.docker)
        self.assertIn('href=\\\"/admin/markets.html\\\"', self.docker)
        self.assertNotIn("RUN rm -rf /data", self.docker)

if __name__ == "__main__":
    unittest.main()
