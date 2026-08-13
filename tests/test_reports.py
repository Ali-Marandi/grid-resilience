import tempfile
import unittest
from pathlib import Path

from grid_resilience import ResilienceEngine, sample_network
from grid_resilience_reports import REPORT_LIMITATION, export_html_report, export_pdf_report


class ReportTests(unittest.TestCase):
    def test_html_and_pdf_reports_include_provenance_and_limitation(self) -> None:
        network = sample_network()
        summary = ResilienceEngine().analyse(network)
        with tempfile.TemporaryDirectory() as temporary:
            html = Path(temporary) / "report.html"
            pdf = Path(temporary) / "report.pdf"
            export_html_report(html, network, summary, None, None)
            export_pdf_report(pdf, network, summary, None, None)
            self.assertIn(network.name, html.read_text(encoding="utf-8"))
            self.assertIn(REPORT_LIMITATION, html.read_text(encoding="utf-8"))
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
