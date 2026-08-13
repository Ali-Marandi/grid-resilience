"""Audit-friendly engineering report exports for Grid Resilience Control Center."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from grid_resilience import AnalysisSummary, NetworkModel
from grid_resilience_advanced import N2AnalysisSummary
from grid_resilience_transient import TransientSimulationResult

if TYPE_CHECKING:
    from collections.abc import Iterable


REPORT_LIMITATION = (
    "This report contains engineering screening results. Multi-generator transient results are reduced-order, "
    "balanced positive-sequence screening only and must not be the sole basis for protection or operational decisions."
)


def _report_lines(
    network: NetworkModel,
    n1: AnalysisSummary | None,
    n2: N2AnalysisSummary | None,
    transient: TransientSimulationResult | None,
) -> list[tuple[str, str]]:
    generated = datetime.now(timezone.utc).isoformat()
    rows = [("Generated UTC", generated), ("Network", network.name), ("Model schema", network.schema), ("Base", f"{network.base_mva:g} MVA"), ("Model assets", f"{len(network.buses)} buses · {len(network.branches)} branches · {len(network.generators)} generators")]
    if n1:
        rows.extend([("N-1 resilience index", f"{n1.resilience_index:.1f}/100"), ("N-1 contingencies", str(len(n1.contingencies))), ("N-1 maximum loading", f"{n1.base_case.max_loading_pct:.2f}%")])
    if n2:
        rows.extend([("N-2 contingencies", str(len(n2.results))), ("Highest N-2 severity", f"{n2.ranked[0].severity_score:.2f}" if n2.ranked else "—")])
    if transient:
        rows.extend([("Transient event", transient.fault_id), ("Transient status", transient.status.value), ("Maximum rotor-angle separation", f"{transient.max_angle_separation_deg:.2f} degrees"), ("Maximum speed deviation", f"{transient.max_speed_deviation_pu:.5f} pu")])
    return rows


def export_html_report(
    path: str | Path,
    network: NetworkModel,
    n1: AnalysisSummary | None,
    n2: N2AnalysisSummary | None,
    transient: TransientSimulationResult | None,
) -> None:
    rows = _report_lines(network, n1, n2, transient)
    body = "\n".join(f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>" for label, value in rows)
    content = f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Grid Resilience Control Center report</title><style>body{{font-family:Segoe UI,Arial,sans-serif;color:#172b4d;margin:36px;line-height:1.45}}h1{{margin-bottom:0}}.sub{{color:#5f6b7a}}table{{border-collapse:collapse;width:100%;max-width:850px;margin:24px 0}}th,td{{padding:10px 12px;border:1px solid #d7e0ea;text-align:left}}th{{width:34%;background:#f5f8fc}}.notice{{border-left:4px solid #b7791f;background:#fff4e5;padding:14px 16px;max-width:850px}}</style></head><body><h1>Grid Resilience Control Center</h1><p class=\"sub\">Engineering screening report with model provenance and limitations</p><table>{body}</table><div class=\"notice\"><strong>Engineering limitation.</strong> {escape(REPORT_LIMITATION)}</div></body></html>"""
    Path(path).write_text(content, encoding="utf-8")


def export_pdf_report(
    path: str | Path,
    network: NetworkModel,
    n1: AnalysisSummary | None,
    n2: N2AnalysisSummary | None,
    transient: TransientSimulationResult | None,
) -> None:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(0, 10, "Grid Resilience Control Center")
    pdf.ln(10)
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(0, 6, "Engineering screening report with model provenance and limitations")
    pdf.ln(3)
    for label, value in _report_lines(network, n1, n2, transient):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, f"{label}:".encode("latin-1", "replace").decode("latin-1"))
        pdf.ln(6)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, value.encode("latin-1", "replace").decode("latin-1"))
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "Engineering limitation")
    pdf.ln(7)
    pdf.set_font("Helvetica", size=9)
    pdf.multi_cell(0, 6, REPORT_LIMITATION.encode("latin-1", "replace").decode("latin-1"))
    pdf.output(str(path))
