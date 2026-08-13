"""Desktop application for Grid Resilience Studio."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from grid_resilience import (
    AnalysisSummary,
    CORE_VERSION,
    NetworkModel,
    ProjectStore,
    ResilienceEngine,
    ResultStatus,
    ValidationError,
    export_results_csv,
    sample_network,
)
from grid_resilience_ac import ACPowerFlowEngine, ACPowerFlowResult, EconomicDispatchEngine, OperationalOptimizationResult
from grid_resilience_import import CIMCGMESImporter, IEECDFImporter, ImportReport
from grid_resilience_security import (
    AuthorizationError, HashChainedAuditLog, LocalIdentityStore, Permission, Principal,
    Role, require,
)
from grid_resilience_advanced import AdvancedContingencyEngine, N2AnalysisSummary
from grid_resilience_transient import FaultEvent, TransientSimulationResult, TransientStabilityEngine
from grid_resilience_reports import export_html_report, export_pdf_report

APP_NAME = "Grid Resilience Studio"
APP_VERSION = CORE_VERSION

COLORS = {
    "navy": "#0B1F35", "surface": "#F5F8FC", "white": "#FFFFFF", "ink": "#172B4D",
    "muted": "#5F6B7A", "line": "#D7E0EA", "blue": "#2476D3", "teal": "#00A59A",
    "green": "#17825D", "amber": "#B7791F", "red": "#C93838", "slate": "#334E68",
}


class MetricCard(ttk.Frame):
    def __init__(self, master: tk.Misc, title: str, value: str, accent: str) -> None:
        super().__init__(master, style="Card.TFrame", padding=(16, 12))
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text=title.upper(), style="MetricLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.value_var = tk.StringVar(value=value)
        ttk.Label(self, textvariable=self.value_var, style="MetricValue.TLabel", foreground=accent).grid(row=1, column=0, sticky="w", pady=(5, 0))

    def set(self, value: str) -> None:
        self.value_var.set(value)


class GridResilienceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1420x880")
        self.minsize(1160, 720)
        self.configure(bg=COLORS["surface"])
        self.engine = ResilienceEngine()
        self.ac_engine = ACPowerFlowEngine()
        self.dispatch_engine = EconomicDispatchEngine()
        self.transient_engine = TransientStabilityEngine()
        self.advanced_engine = AdvancedContingencyEngine()
        self.network: NetworkModel = sample_network()
        self.summary: AnalysisSummary | None = None
        self.ac_result: ACPowerFlowResult | None = None
        self.opf_result: OperationalOptimizationResult | None = None
        self.import_report: ImportReport | None = None
        self.transient_result: TransientSimulationResult | None = None
        self.n2_summary: N2AnalysisSummary | None = None
        self._canvas_positions: dict[str, tuple[float, float]] = {}
        self._topology_preview: dict[str, tuple[float, float]] = {}
        self._dragged_bus_id: str | None = None
        self._dark_mode = False
        self._detached_topology_canvas: tk.Canvas | None = None
        self._detached_transient_canvas: tk.Canvas | None = None
        self.project_path: Path | None = None
        self.audit: list[str] = []
        security_root = Path.home() / ".grid-resilience-studio"
        self.identity_store = LocalIdentityStore(security_root / "identities.json")
        self.audit_log = HashChainedAuditLog(security_root / "audit.jsonl")
        self.principal: Principal | None = None
        self._configure_style()
        self._build_menu()
        self._build_layout()
        self._log("Application started with the validated demonstration project.")
        self._refresh_all()
        self.after_idle(self._sign_in_or_bootstrap)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["surface"])
        style.configure("Panel.TFrame", background=COLORS["white"])
        style.configure("Card.TFrame", background=COLORS["white"], relief="solid", borderwidth=1)
        style.configure("TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=COLORS["white"])
        style.configure("Title.TLabel", background=COLORS["navy"], foreground=COLORS["white"], font=("Segoe UI Semibold", 20))
        style.configure("Subtitle.TLabel", background=COLORS["navy"], foreground="#BFD1E6", font=("Segoe UI", 9))
        style.configure("MetricLabel.TLabel", background=COLORS["white"], foreground=COLORS["muted"], font=("Segoe UI Semibold", 8))
        style.configure("MetricValue.TLabel", background=COLORS["white"], font=("Segoe UI Semibold", 20))
        style.configure("Section.TLabel", background=COLORS["white"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 12))
        style.configure("TButton", font=("Segoe UI Semibold", 9), padding=(10, 7))
        style.configure("Primary.TButton", background=COLORS["blue"], foreground=COLORS["white"])
        style.map("Primary.TButton", background=[("active", "#175FAF")])
        style.configure("Secondary.TButton", background="#EAF1F8", foreground=COLORS["ink"])
        style.map("Secondary.TButton", background=[("active", "#DCE9F5")])
        style.configure("Treeview", background=COLORS["white"], fieldbackground=COLORS["white"], foreground=COLORS["ink"], rowheight=30, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#EAF1F8", foreground=COLORS["slate"], font=("Segoe UI Semibold", 9), relief="flat")
        style.map("Treeview", background=[("selected", "#DDEBFA")], foreground=[("selected", COLORS["ink"])])
        style.configure("TNotebook", background=COLORS["white"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 9), font=("Segoe UI Semibold", 9), background="#EAF1F8", foreground=COLORS["slate"])
        style.map("TNotebook.Tab", background=[("selected", COLORS["white"])], foreground=[("selected", COLORS["blue"])])

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        COLORS.update({
            "surface": "#17212B", "white": "#22313F", "ink": "#E8F0F7", "muted": "#AABCCD", "line": "#3B4F60", "navy": "#071722", "blue": "#57A7FF", "teal": "#2DD4BF", "green": "#5EE0A6", "amber": "#F0B45C", "red": "#FF7D7D", "slate": "#C1D6E8",
        } if self._dark_mode else {
            "surface": "#F5F8FC", "white": "#FFFFFF", "ink": "#172B4D", "muted": "#5F6B7A", "line": "#D7E0EA", "navy": "#0B1F35", "blue": "#2476D3", "teal": "#00A59A", "green": "#17825D", "amber": "#B7791F", "red": "#C93838", "slate": "#334E68",
        })
        self.configure(bg=COLORS["surface"])
        self._configure_style()
        self.network_canvas.configure(bg="#1A2733" if self._dark_mode else "#FBFDFF")
        if hasattr(self, "transient_canvas"):
            self.transient_canvas.configure(bg="#1A2733" if self._dark_mode else "#FBFDFF")
        self._draw_network()
        self._draw_transient()
        self.status_var.set("Dark theme enabled." if self._dark_mode else "Light theme enabled.")

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        project = tk.Menu(menu, tearoff=False)
        project.add_command(label="New demonstration project", command=self._new_sample)
        project.add_command(label="Open project…", command=self._open_project)
        project.add_command(label="Save project", command=self._save_project)
        project.add_command(label="Save project as…", command=lambda: self._save_project(force_dialog=True))
        project.add_separator()
        project.add_command(label="Import IEEE CDF…", command=self._import_cdf)
        project.add_command(label="Import CIM/CGMES…", command=self._import_cgmes)
        project.add_separator()
        project.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="Project", menu=project)
        analysis = tk.Menu(menu, tearoff=False)
        analysis.add_command(label="Validate model", command=self._validate_model)
        analysis.add_command(label="Run N-1 screening", command=self._run_analysis)
        analysis.add_command(label="Run balanced AC power flow", command=self._run_ac_power_flow)
        analysis.add_command(label="Run economic dispatch + AC validation", command=self._run_operational_optimization)
        analysis.add_command(label="Run transient stability screening…", command=self._run_transient_stability)
        analysis.add_command(label="Run N-2 and cascade screening", command=self._run_n2_analysis)
        analysis.add_command(label="Export contingency CSV…", command=self._export_csv)
        analysis.add_command(label="Export HTML engineering report…", command=self._export_html_report)
        analysis.add_command(label="Export PDF engineering report…", command=self._export_pdf_report)
        menu.add_cascade(label="Analysis", menu=analysis)
        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_command(label="Toggle light / dark theme", command=self._toggle_theme)
        view_menu.add_command(label="Detach topology editor", command=self._detach_topology_editor)
        view_menu.add_command(label="Detach transient swing curves", command=self._detach_transient_panel)
        menu.add_cascade(label="View", menu=view_menu)
        security_menu = tk.Menu(menu, tearoff=False)
        security_menu.add_command(label="Sign in / switch user…", command=self._sign_in_or_bootstrap)
        security_menu.add_command(label="Create local user…", command=self._create_local_user)
        security_menu.add_command(label="Verify audit chain", command=self._verify_audit_chain)
        menu.add_cascade(label="Security", menu=security_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Methodology and limitations", command=self._show_methodology)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo(APP_NAME, f"{APP_NAME} {APP_VERSION}\nDeterministic local engineering screening."))
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

    def _build_layout(self) -> None:
        header = ttk.Frame(self, style="Panel.TFrame")
        header.configure(style="Panel.TFrame")
        header.pack(fill="x")
        banner = tk.Frame(header, bg=COLORS["navy"], height=86)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text=APP_NAME, bg=COLORS["navy"], fg=COLORS["white"], font=("Segoe UI Semibold", 21)).pack(anchor="w", padx=24, pady=(16, 0))
        self.project_title = tk.StringVar()
        tk.Label(banner, textvariable=self.project_title, bg=COLORS["navy"], fg="#BFD1E6", font=("Segoe UI", 9)).pack(anchor="w", padx=25, pady=(2, 0))
        top = ttk.Frame(self, padding=(18, 16, 18, 8))
        top.pack(fill="x")
        top.columnconfigure((0, 1, 2, 3), weight=1, uniform="metric")
        self.metric_resilience = MetricCard(top, "Resilience index", "—", COLORS["blue"])
        self.metric_secure = MetricCard(top, "Secure scenarios", "—", COLORS["green"])
        self.metric_risk = MetricCard(top, "Risk scenarios", "—", COLORS["red"])
        self.metric_loading = MetricCard(top, "Base max loading", "—", COLORS["amber"])
        for index, card in enumerate((self.metric_resilience, self.metric_secure, self.metric_risk, self.metric_loading)):
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
        body = ttk.Frame(self, padding=(18, 8, 18, 18))
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_sidebar(body)
        self._build_workspace(body)
        self._build_statusbar()

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        side = ttk.Frame(parent, style="Panel.TFrame", padding=16, width=245)
        side.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        side.grid_propagate(False)
        ttk.Label(side, text="WORKSPACE", style="Section.TLabel").pack(anchor="w")
        ttk.Label(side, text="Local project controls and engineering workflow.", style="Panel.TLabel", foreground=COLORS["muted"], wraplength=205).pack(anchor="w", pady=(5, 18))
        self._side_button(side, "Run N-1 screening", self._run_analysis, primary=True)
        self._side_button(side, "Run AC power flow", self._run_ac_power_flow)
        self._side_button(side, "Economic dispatch + AC check", self._run_operational_optimization)
        self._side_button(side, "Run transient stability", self._run_transient_stability)
        self._side_button(side, "Run N-2 + cascade screening", self._run_n2_analysis)
        self._side_button(side, "Import IEEE CDF", self._import_cdf)
        self._side_button(side, "Import CIM/CGMES", self._import_cgmes)
        self._side_button(side, "Validate model", self._validate_model)
        self._side_button(side, "Edit model data", self._edit_model)
        self._side_button(side, "Open project", self._open_project)
        self._side_button(side, "Save project", self._save_project)
        ttk.Separator(side).pack(fill="x", pady=16)
        ttk.Label(side, text="GOVERNANCE", style="Section.TLabel").pack(anchor="w")
        ttk.Label(side, text="Every analysis run records the engine version, timestamp and screening outcomes in this session.", style="Panel.TLabel", foreground=COLORS["muted"], wraplength=205).pack(anchor="w", pady=(5, 12))
        self._side_button(side, "Export ranked CSV", self._export_csv)
        self._side_button(side, "Export HTML report", self._export_html_report)
        self._side_button(side, "Export PDF report", self._export_pdf_report)
        self._side_button(side, "View audit trail", self._show_audit)
        ttk.Separator(side).pack(fill="x", pady=16)
        tk.Label(side, text="ENGINEERING SCREENING ONLY", bg="#FFF4E5", fg="#8C4D00", font=("Segoe UI Semibold", 8), padx=8, pady=6).pack(anchor="w", fill="x")
        ttk.Label(side, text="DC and balanced AC screening do not replace approved protection, short-circuit or dynamic studies.", style="Panel.TLabel", foreground=COLORS["muted"], wraplength=205).pack(anchor="w", pady=(8, 0))

    def _side_button(self, parent: ttk.Frame, title: str, command: Callable[[], None], primary: bool = False) -> None:
        ttk.Button(parent, text=title, command=command, style="Primary.TButton" if primary else "Secondary.TButton").pack(fill="x", pady=(0, 8))

    def _build_workspace(self, parent: ttk.Frame) -> None:
        workspace = ttk.Frame(parent, style="Panel.TFrame", padding=0)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.rowconfigure(0, weight=1)
        workspace.columnconfigure(0, weight=1)
        notebook = ttk.Notebook(workspace)
        notebook.grid(row=0, column=0, sticky="nsew")
        overview = ttk.Frame(notebook, style="Panel.TFrame", padding=18)
        contingencies = ttk.Frame(notebook, style="Panel.TFrame", padding=18)
        data_quality = ttk.Frame(notebook, style="Panel.TFrame", padding=18)
        transient = ttk.Frame(notebook, style="Panel.TFrame", padding=18)
        n2_cases = ttk.Frame(notebook, style="Panel.TFrame", padding=18)
        topology = ttk.Frame(notebook, style="Panel.TFrame", padding=18)
        notebook.add(overview, text="Network overview")
        notebook.add(contingencies, text="Contingency queue")
        notebook.add(data_quality, text="Model quality")
        notebook.add(transient, text="Transient stability")
        notebook.add(n2_cases, text="N-2 & cascades")
        notebook.add(topology, text="Topology editor")
        self._build_overview(overview)
        self._build_contingencies(contingencies)
        self._build_data_quality(data_quality)
        self._build_transient(transient)
        self._build_n2(n2_cases)
        self._build_topology_editor(topology)

    def _build_overview(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="System topology and base-case loading", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.overview_caption = ttk.Label(parent, text="Run analysis to overlay power-flow utilisation and identify risk pathways.", style="Panel.TLabel", foreground=COLORS["muted"])
        self.overview_caption.grid(row=0, column=1, sticky="e")
        canvas_panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        canvas_panel.grid(row=1, column=0, sticky="nsew", pady=(14, 0), padx=(0, 14))
        canvas_panel.rowconfigure(0, weight=1)
        canvas_panel.columnconfigure(0, weight=1)
        self.network_canvas = tk.Canvas(canvas_panel, bg="#FBFDFF", highlightthickness=0)
        self.network_canvas.grid(row=0, column=0, sticky="nsew")
        self.network_canvas.bind("<Configure>", lambda event: self._draw_network())
        self.network_canvas.bind("<ButtonPress-1>", self._topology_press)
        self.network_canvas.bind("<B1-Motion>", self._topology_drag)
        self.network_canvas.bind("<ButtonRelease-1>", self._topology_release)
        insights = ttk.Frame(parent, style="Card.TFrame", padding=16)
        insights.grid(row=1, column=1, sticky="nsew", pady=(14, 0))
        ttk.Label(insights, text="Decision brief", style="Section.TLabel").pack(anchor="w")
        self.decision_brief = tk.Text(insights, height=17, wrap="word", relief="flat", bg=COLORS["white"], fg=COLORS["ink"], font=("Segoe UI", 10), padx=0, pady=10)
        self.decision_brief.pack(fill="both", expand=True)
        self.decision_brief.configure(state="disabled")

    def _build_contingencies(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(toolbar, text="Ranked N-1 contingency queue", style="Section.TLabel").pack(side="left")
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv, style="Secondary.TButton").pack(side="right")
        ttk.Button(toolbar, text="Run analysis", command=self._run_analysis, style="Primary.TButton").pack(side="right", padx=(0, 8))
        columns = ("rank", "status", "element", "severity", "max_loading", "unserved", "message")
        self.contingency_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        headings = {
            "rank": ("Rank", 60), "status": ("Outcome", 105), "element": ("Outaged element", 215),
            "severity": ("Severity", 100), "max_loading": ("Max loading", 105), "unserved": ("Unserved MW", 105), "message": ("Assessment", 330),
        }
        for key, (label, width) in headings.items():
            self.contingency_tree.heading(key, text=label)
            self.contingency_tree.column(key, width=width, anchor="w" if key in {"element", "message"} else "center", stretch=key == "message")
        self.contingency_tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=self.contingency_tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.contingency_tree.configure(yscrollcommand=scroll.set)
        self.contingency_tree.tag_configure("secure", foreground=COLORS["green"])
        self.contingency_tree.tag_configure("violation", foreground=COLORS["red"])
        self.contingency_tree.tag_configure("islanded", foreground=COLORS["amber"])
        self.contingency_tree.tag_configure("unsolved", foreground=COLORS["red"])

    def _build_data_quality(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        ttk.Label(parent, text="Validation, provenance and model governance", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="The project schema performs deterministic checks before analysis. The data model is locally portable JSON with stable identifiers.", style="Panel.TLabel", foreground=COLORS["muted"], wraplength=800).grid(row=1, column=0, sticky="w", pady=(5, 14))
        self.quality_text = tk.Text(parent, wrap="word", relief="solid", bd=1, bg="#FBFDFF", fg=COLORS["ink"], font=("Cascadia Mono", 9), padx=12, pady=12)
        self.quality_text.grid(row=2, column=0, sticky="nsew")
        self.quality_text.configure(state="disabled")

    def _build_transient(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        header = ttk.Frame(parent, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(header, text="Rotor-angle and rotor-speed screening", style="Section.TLabel").pack(side="left")
        ttk.Button(header, text="Run event", command=self._run_transient_stability, style="Primary.TButton").pack(side="right")
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)
        self.transient_canvas = tk.Canvas(panel, bg="#FBFDFF", highlightthickness=0)
        self.transient_canvas.grid(row=0, column=0, sticky="nsew")
        self.transient_canvas.bind("<Configure>", lambda event: self._draw_transient())
        self.transient_caption = tk.StringVar(value="Run a fault application and clearing event to render multi-generator swing curves.")
        ttk.Label(parent, textvariable=self.transient_caption, style="Panel.TLabel", foreground=COLORS["muted"], wraplength=900).grid(row=2, column=0, sticky="w", pady=(10, 0))

    def _build_n2(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(toolbar, text="Ranked N-2 and overload-cascade screening", style="Section.TLabel").pack(side="left")
        ttk.Button(toolbar, text="Run N-2", command=self._run_n2_analysis, style="Primary.TButton").pack(side="right")
        columns = ("rank", "pair", "status", "severity", "loading", "cascade", "action")
        self.n2_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        headings = {"rank": ("Rank", 55), "pair": ("Outaged pair", 230), "status": ("Outcome", 100), "severity": ("Severity", 90), "loading": ("Max loading", 105), "cascade": ("Cascade", 85), "action": ("Review suggestion", 360)}
        for key, (label, width) in headings.items():
            self.n2_tree.heading(key, text=label)
            self.n2_tree.column(key, width=width, anchor="w" if key in {"pair", "action"} else "center", stretch=key == "action")
        self.n2_tree.grid(row=1, column=0, sticky="nsew")

    def _build_topology_editor(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(toolbar, text="Drag buses to position the local topology", style="Section.TLabel").pack(side="left")
        ttk.Button(toolbar, text="Detach panel", command=self._detach_topology_editor, style="Secondary.TButton").pack(side="right")
        self.topology_canvas = tk.Canvas(parent, bg="#FBFDFF", highlightthickness=0)
        self.topology_canvas.grid(row=1, column=0, sticky="nsew")
        self.topology_canvas.bind("<Configure>", lambda event: self._draw_topology_editor())
        self.topology_canvas.bind("<ButtonPress-1>", self._topology_press)
        self.topology_canvas.bind("<B1-Motion>", self._topology_drag)
        self.topology_canvas.bind("<ButtonRelease-1>", self._topology_release)

    def _build_statusbar(self) -> None:
        frame = tk.Frame(self, bg=COLORS["navy"], height=28)
        frame.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(frame, textvariable=self.status_var, bg=COLORS["navy"], fg="#D7E7F7", font=("Segoe UI", 8), anchor="w", padx=16).pack(fill="x")

    def _refresh_all(self) -> None:
        self.project_title.set(f"{self.network.name}  ·  Local project  ·  Base: {self.network.base_mva:g} MVA")
        self._refresh_quality()
        self._draw_network()
        self._refresh_summary()

    def _refresh_quality(self) -> None:
        issues = self.network.validate()
        text = [
            f"Schema: {self.network.schema}", f"Network: {self.network.name}",
            f"Assets: {len(self.network.buses)} buses, {len(self.network.branches)} branches, {len(self.network.generators)} generators", "",
        ]
        if issues:
            text.append("VALIDATION FAILED")
            text.extend(f"• {item}" for item in issues)
        else:
            text.append("VALIDATION PASSED")
            text.append("• Exactly one slack bus is defined.")
            text.append("• All asset identifiers are unique and all references resolve.")
            text.append("• Branch reactance and thermal limits are strictly positive.")
            text.append("• Generator dispatch respects declared maximum output.")
            text.append("")
            text.append("Provenance notes")
            text.append("• Project data remains local unless you explicitly export or save it.")
            text.append("• Results are deterministic for the same project and engine version.")
            text.append("• DC screening results must be independently reviewed before operational use.")
        self.quality_text.configure(state="normal")
        self.quality_text.delete("1.0", "end")
        self.quality_text.insert("1.0", "\n".join(text))
        self.quality_text.configure(state="disabled")

    def _refresh_summary(self) -> None:
        if self.summary is None:
            self.metric_resilience.set("Not run")
            self.metric_secure.set("—")
            self.metric_risk.set("—")
            self.metric_loading.set("—")
            self._set_brief("No N-1 screening has been executed. Validate the model and run the analysis to generate a ranked engineering decision brief.")
            return
        summary = self.summary
        total = len(summary.contingencies)
        risk = summary.violation_count + summary.islanded_count + summary.unsolved_count
        self.metric_resilience.set(f"{summary.resilience_index:.1f}/100")
        self.metric_secure.set(f"{summary.secure_count}/{total}")
        self.metric_risk.set(f"{risk}/{total}")
        self.metric_loading.set(f"{summary.base_case.max_loading_pct:.1f}%")
        ranked = summary.ranked
        critical = ranked[0] if ranked else None
        brief = [
            f"Screening completed at {summary.analysed_at.replace('T', ' ')[:19]} UTC.", "",
            f"The deterministic DC engine screened {total} single-element outages. The resilience index is {summary.resilience_index:.1f}/100; {summary.secure_count} cases meet branch thermal limits, while {risk} cases require engineering review.", "",
        ]
        if critical:
            brief.append("Highest-priority review")
            brief.append(f"{critical.id} — {critical.element_name}")
            brief.append(f"Outcome: {critical.status.value.replace('_', ' ').title()}")
            brief.append(f"Assessment: {critical.message}")
            if critical.unserved_load_mw:
                brief.append(f"Potential unserved load: {critical.unserved_load_mw:.1f} MW")
        brief.extend(["", "Recommended next step", "Review the ranked queue, verify input assumptions, then perform approved AC, protection and dynamic studies before any operating decision."])
        self._set_brief("\n".join(brief))

    def _set_brief(self, text: str) -> None:
        self.decision_brief.configure(state="normal")
        self.decision_brief.delete("1.0", "end")
        self.decision_brief.insert("1.0", text)
        self.decision_brief.configure(state="disabled")

    def _draw_network(self) -> None:
        canvas = self.network_canvas
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        width, height = max(canvas.winfo_width(), 500), max(canvas.winfo_height(), 400)
        positions: dict[str, tuple[float, float]] = {}
        for index, bus in enumerate(self.network.buses):
            x = bus.x if bus.x is not None else 80 + (index % 3) * 150
            y = bus.y if bus.y is not None else 100 + (index // 3) * 140
            positions[bus.id] = (x / 500 * (width - 100) + 50, y / 380 * (height - 100) + 50)
        self._canvas_positions = positions
        if self.ac_result is not None:
            flow_map = {flow.branch_id: flow for flow in self.ac_result.branches}
        elif self.summary is not None:
            flow_map = {flow.branch_id: flow for flow in self.summary.base_case.branch_flows}
        else:
            flow_map = {}
        for branch in self.network.branches:
            if branch.from_bus not in positions or branch.to_bus not in positions:
                continue
            x1, y1 = positions[branch.from_bus]
            x2, y2 = positions[branch.to_bus]
            flow = flow_map.get(branch.id)
            loading = flow.loading_pct if flow else 0.0
            color = COLORS["red"] if loading > 100 else COLORS["amber"] if loading > 85 else COLORS["teal"]
            canvas.create_line(x1, y1, x2, y2, fill=color, width=4 if loading > 85 else 3, capstyle="round")
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            caption = f"{branch.id}\n{loading:.0f}%" if flow_map else branch.id
            canvas.create_text(mx, my - 13, text=caption, fill=COLORS["muted"], font=("Segoe UI", 8), justify="center")
        for bus in self.network.buses:
            x, y = positions[bus.id]
            fill = COLORS["blue"] if bus.is_slack else COLORS["white"]
            outline = COLORS["blue"] if bus.is_slack else COLORS["slate"]
            canvas.create_oval(x - 22, y - 22, x + 22, y + 22, fill=fill, outline=outline, width=3)
            canvas.create_text(x, y, text="S" if bus.is_slack else bus.id.replace("B", ""), fill=COLORS["white"] if bus.is_slack else COLORS["ink"], font=("Segoe UI Semibold", 10))
            canvas.create_text(x, y + 38, text=f"{bus.name}\n{bus.load_mw:g} MW load", fill=COLORS["ink"], font=("Segoe UI", 8), justify="center")
        legend_y = height - 25
        for index, (label, color) in enumerate((("<85% normal", COLORS["teal"]), ("85–100% watch", COLORS["amber"]), (">100% violation", COLORS["red"]))):
            x = 22 + index * 150
            canvas.create_rectangle(x, legend_y - 5, x + 11, legend_y + 6, fill=color, outline=color)
            canvas.create_text(x + 18, legend_y, text=label, anchor="w", fill=COLORS["muted"], font=("Segoe UI", 8))
        if hasattr(self, "topology_canvas"):
            self._draw_topology_editor()

    def _draw_topology_editor(self, target: tk.Canvas | None = None) -> None:
        canvas = target or getattr(self, "topology_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        width, height = max(canvas.winfo_width(), 500), max(canvas.winfo_height(), 360)
        positions: dict[str, tuple[float, float]] = {}
        for index, bus in enumerate(self.network.buses):
            x = bus.x if bus.x is not None else 80 + (index % 3) * 150
            y = bus.y if bus.y is not None else 100 + (index // 3) * 140
            positions[bus.id] = (x / 500 * (width - 100) + 50, y / 380 * (height - 100) + 50)
        self._topology_preview = positions
        for branch in self.network.branches:
            if branch.from_bus in positions and branch.to_bus in positions:
                canvas.create_line(*positions[branch.from_bus], *positions[branch.to_bus], fill=COLORS["line"], width=3, capstyle="round")
        for bus in self.network.buses:
            x, y = positions[bus.id]
            canvas.create_oval(x - 24, y - 24, x + 24, y + 24, fill=COLORS["blue"] if bus.is_slack else COLORS["white"], outline=COLORS["teal"], width=3, tags=(f"bus:{bus.id}",))
            canvas.create_text(x, y, text=bus.id, fill=COLORS["white"] if bus.is_slack else COLORS["ink"], font=("Segoe UI Semibold", 9), tags=(f"bus:{bus.id}",))
            canvas.create_text(x, y + 38, text=bus.name, fill=COLORS["ink"], font=("Segoe UI", 8), tags=(f"bus:{bus.id}",))
        canvas.create_text(16, height - 18, anchor="w", text="Drag a bus to update its local position. Save the project to persist it.", fill=COLORS["muted"], font=("Segoe UI", 8))

    def _topology_press(self, event: tk.Event[tk.Misc]) -> None:
        topology_canvases = (getattr(self, "topology_canvas", None), self._detached_topology_canvas)
        positions = self._topology_preview if event.widget in topology_canvases else self._canvas_positions
        for bus_id, (x, y) in positions.items():
            if (event.x - x) ** 2 + (event.y - y) ** 2 <= 32 ** 2:
                self._dragged_bus_id = bus_id
                return

    def _topology_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._dragged_bus_id is None:
            return
        canvas = event.widget
        width, height = max(canvas.winfo_width(), 500), max(canvas.winfo_height(), 360)
        x = max(0.0, min(500.0, (event.x - 50) / max(1, width - 100) * 500))
        y = max(0.0, min(380.0, (event.y - 50) / max(1, height - 100) * 380))
        self.network.buses = [replace(bus, x=round(x, 2), y=round(y, 2)) if bus.id == self._dragged_bus_id else bus for bus in self.network.buses]
        self._draw_network()
        self._draw_topology_editor()
        self._draw_topology_editor(self._detached_topology_canvas)

    def _topology_release(self, event: tk.Event[tk.Misc]) -> None:
        if self._dragged_bus_id is not None:
            self._record("topology_position", "success", self._dragged_bus_id)
            self.status_var.set(f"Updated local position for {self._dragged_bus_id}; save the project to persist it.")
        self._dragged_bus_id = None

    def _run_transient_stability(self) -> None:
        if not self._authorize(Permission.RUN_SCREENING):
            return
        clearing = simpledialog.askfloat(APP_NAME, "Fault clearing time in seconds (screening):", initialvalue=0.20, minvalue=0.06, maxvalue=2.0, parent=self)
        if clearing is None:
            return
        try:
            fault = FaultEvent("UI-FAULT", apply_time_s=0.05, clear_time_s=clearing, severity=0.72, description="User-defined balanced fault screening")
            self.transient_result = self.transient_engine.simulate(self.network, fault, duration_s=max(2.0, clearing + 1.2))
            cct = self.transient_engine.critical_clearing_time(self.network, fault, duration_s=max(1.5, clearing + 1.0), search_max_s=min(1.0, max(clearing + 0.25, 0.35)), iterations=8)
            self.transient_caption.set(f"Status: {self.transient_result.status.value}; maximum separation {self.transient_result.max_angle_separation_deg:.1f}°; CCT screening bound {cct.critical_clearing_time_s:.3f} s. {self.transient_result.disclaimer}")
            self._record("transient_stability", self.transient_result.status.value, f"clear={clearing:.3f}s; cct={cct.critical_clearing_time_s:.3f}s")
            self._swing_frame_index = 2
            self._transient_animation_token = getattr(self, "_transient_animation_token", 0) + 1
            self._animate_transient(self._transient_animation_token)
            self.status_var.set("Transient stability screening completed; review disclaimer and assumptions.")
        except (ValidationError, RuntimeError, ValueError) as exc:
            self._record("transient_stability", "failed", str(exc))
            messagebox.showerror(APP_NAME, f"Transient stability screening could not complete.\n\n{exc}")

    def _animate_transient(self, token: int) -> None:
        if token != getattr(self, "_transient_animation_token", token) or self.transient_result is None:
            return
        self._draw_transient(limit=self._swing_frame_index)
        self._draw_transient(limit=self._swing_frame_index, target=self._detached_transient_canvas)
        if self._swing_frame_index < len(self.transient_result.points):
            self._swing_frame_index = min(len(self.transient_result.points), self._swing_frame_index + 4)
            self.after(24, lambda: self._animate_transient(token))

    def _draw_transient(self, limit: int | None = None, target: tk.Canvas | None = None) -> None:
        canvas = target or getattr(self, "transient_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        width, height = max(canvas.winfo_width(), 520), max(canvas.winfo_height(), 320)
        result = self.transient_result
        if result is None or not result.points:
            canvas.create_text(width / 2, height / 2, text="Run a transient stability event to animate generator swing curves.", fill=COLORS["muted"], font=("Segoe UI", 10))
            return
        points = result.points[:limit] if limit is not None else result.points
        all_angles = [value for point in result.points for value in point.rotor_angles_deg.values()]
        minimum, maximum = min(all_angles) - 5, max(all_angles) + 5
        left, right, top, bottom = 58, width - 28, 26, height - 42
        canvas.create_line(left, top, left, bottom, fill=COLORS["line"])
        canvas.create_line(left, bottom, right, bottom, fill=COLORS["line"])
        colors = [COLORS["blue"], COLORS["teal"], COLORS["amber"], COLORS["red"]]
        duration = max(result.points[-1].time_s, 0.001)
        span = max(1.0, maximum - minimum)
        for index, generator_id in enumerate(result.points[0].rotor_angles_deg):
            curve: list[float] = []
            for point in points:
                curve.extend((left + point.time_s / duration * (right - left), bottom - (point.rotor_angles_deg[generator_id] - minimum) / span * (bottom - top)))
            if len(curve) >= 4:
                canvas.create_line(*curve, fill=colors[index % len(colors)], width=2, smooth=True)
            canvas.create_text(right - 3, top + 15 * index, anchor="e", text=generator_id, fill=colors[index % len(colors)], font=("Segoe UI Semibold", 8))
        canvas.create_text(left, 12, anchor="w", text="Rotor angle (degrees) · animated screening trace", fill=COLORS["muted"], font=("Segoe UI", 8))
        canvas.create_text(right, bottom + 22, anchor="e", text=f"0 to {duration:.2f} seconds", fill=COLORS["muted"], font=("Segoe UI", 8))

    def _run_n2_analysis(self) -> None:
        if not self._authorize(Permission.RUN_SCREENING):
            return
        try:
            self.n2_summary = self.advanced_engine.analyse_n2(self.network)
            for item in self.n2_tree.get_children():
                self.n2_tree.delete(item)
            for rank, result in enumerate(self.n2_summary.ranked, start=1):
                pair = ", ".join([*result.outaged_branch_ids, *result.outaged_generator_ids])
                action = result.remedial_actions[0] if result.remedial_actions else "Engineering review required."
                self.n2_tree.insert("", "end", values=(rank, pair, result.status.value.title(), f"{result.severity_score:.1f}", "—" if result.max_loading_pct is None else f"{result.max_loading_pct:.1f}%", len(result.cascade_steps), action))
            self._record("n2_cascade_screening", "success", f"scenarios={len(self.n2_summary.results)}")
            self.status_var.set(f"N-2 screening completed: {len(self.n2_summary.results)} scenarios ranked.")
        except (ValidationError, RuntimeError) as exc:
            self._record("n2_cascade_screening", "failed", str(exc))
            messagebox.showerror(APP_NAME, f"N-2 screening could not complete.\n\n{exc}")

    def _detach_topology_editor(self) -> None:
        existing = getattr(self, "_topology_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
        window = tk.Toplevel(self)
        window.title(f"{APP_NAME} — Detached topology editor")
        window.geometry("860x620")
        window.configure(bg=COLORS["surface"])
        ttk.Label(window, text="Detached topology editor", style="Section.TLabel").pack(anchor="w", padx=16, pady=(16, 3))
        ttk.Label(window, text="Drag buses to update local positions; save the project to persist them.", style="Panel.TLabel", foreground=COLORS["muted"]).pack(anchor="w", padx=16, pady=(0, 10))
        canvas = tk.Canvas(window, bg="#FBFDFF", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._topology_window = window
        self._detached_topology_canvas = canvas
        canvas.bind("<Configure>", lambda event: self._draw_topology_editor(canvas))
        canvas.bind("<ButtonPress-1>", self._topology_press)
        canvas.bind("<B1-Motion>", self._topology_drag)
        canvas.bind("<ButtonRelease-1>", self._topology_release)
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_detached_panel("topology"))
        self._draw_topology_editor(canvas)
        self._record("topology_panel_detached", "success", "window opened")

    def _detach_transient_panel(self) -> None:
        existing = getattr(self, "_transient_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
        window = tk.Toplevel(self)
        window.title(f"{APP_NAME} — Detached transient curves")
        window.geometry("860x520")
        window.configure(bg=COLORS["surface"])
        ttk.Label(window, text="Detached rotor-angle screening curves", style="Section.TLabel").pack(anchor="w", padx=16, pady=(16, 3))
        ttk.Label(window, text="Reduced-order engineering screening only; validate with approved RMS/EMT studies before operational use.", style="Panel.TLabel", foreground=COLORS["muted"], wraplength=800).pack(anchor="w", padx=16, pady=(0, 10))
        canvas = tk.Canvas(window, bg="#FBFDFF", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._transient_window = window
        self._detached_transient_canvas = canvas
        canvas.bind("<Configure>", lambda event: self._draw_transient(target=canvas))
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_detached_panel("transient"))
        self._draw_transient(target=canvas)
        self._record("transient_panel_detached", "success", "window opened")

    def _close_detached_panel(self, kind: str) -> None:
        window = getattr(self, f"_{kind}_window", None)
        if window is not None and window.winfo_exists():
            window.destroy()
        if kind == "topology":
            self._detached_topology_canvas = None
        else:
            self._detached_transient_canvas = None
        setattr(self, f"_{kind}_window", None)

    def _authorize(self, permission: Permission) -> bool:
        if self.principal is None:
            messagebox.showwarning(APP_NAME, "Sign in before performing this operation.")
            self._sign_in_or_bootstrap()
            return False
        try:
            require(self.principal, permission)
            return True
        except AuthorizationError as exc:
            self._record("authorization", "denied", f"{permission.value}: {exc}")
            messagebox.showerror(APP_NAME, f"Access denied.\n\n{exc}")
            return False

    def _record(self, action: str, outcome: str, detail: str = "") -> None:
        actor = self.principal if self.principal is not None else "local-system"
        try:
            self.audit_log.append(actor, action, outcome, detail)
        except OSError:
            pass
        self._log(f"{action}: {outcome}" + (f" — {detail}" if detail else ""))

    def _sign_in_or_bootstrap(self) -> None:
        try:
            if not self.identity_store.exists():
                username = simpledialog.askstring(APP_NAME, "No local identity store exists.\n\nCreate the initial administrator username:", parent=self)
                if not username:
                    return
                password = simpledialog.askstring(APP_NAME, "Create a strong administrator password (12+ characters, 3 character classes):", show="*", parent=self)
                if password is None:
                    return
                confirmation = simpledialog.askstring(APP_NAME, "Confirm administrator password:", show="*", parent=self)
                if password != confirmation:
                    raise ValueError("Password confirmation does not match")
                self.principal = self.identity_store.bootstrap_administrator(username, password)
                self._record("identity_bootstrap", "success", f"administrator {self.principal.username} created")
            else:
                username = simpledialog.askstring(APP_NAME, "Username:", parent=self)
                if not username:
                    return
                password = simpledialog.askstring(APP_NAME, "Password:", show="*", parent=self)
                if password is None:
                    return
                self.principal = self.identity_store.authenticate(username, password)
                self._record("sign_in", "success", f"role={self.principal.role.value}")
            self.status_var.set(f"Signed in as {self.principal.username} ({self.principal.role.value})")
            messagebox.showinfo(APP_NAME, f"Signed in as {self.principal.username} with {self.principal.role.value} role.")
        except (AuthorizationError, ValueError) as exc:
            self._record("sign_in", "failed", str(exc))
            messagebox.showerror(APP_NAME, f"Authentication could not complete.\n\n{exc}")

    def _create_local_user(self) -> None:
        if not self._authorize(Permission.MANAGE_USERS):
            return
        username = simpledialog.askstring(APP_NAME, "New username:", parent=self)
        if not username:
            return
        password = simpledialog.askstring(APP_NAME, "New password (12+ characters, 3 character classes):", show="*", parent=self)
        if password is None:
            return
        role_text = simpledialog.askstring(APP_NAME, "Role: viewer, analyst or operator", initialvalue="analyst", parent=self)
        if not role_text:
            return
        try:
            role = Role(role_text.strip().lower())
            if role is Role.ADMINISTRATOR:
                raise ValueError("Create administrator accounts through the governed identity procedure, not this quick dialog")
            account = self.identity_store.create_user(self.principal, username, password, role)
            self._record("user_create", "success", f"{account.username}:{account.role.value}")
            messagebox.showinfo(APP_NAME, f"Created local {account.role.value} account for {account.username}.")
        except (ValueError, AuthorizationError) as exc:
            self._record("user_create", "failed", str(exc))
            messagebox.showerror(APP_NAME, f"Could not create local user.\n\n{exc}")

    def _verify_audit_chain(self) -> None:
        if not self._authorize(Permission.VIEW_AUDIT):
            return
        valid, message = self.audit_log.verify()
        self._record("audit_verify", "success" if valid else "failed", message)
        (messagebox.showinfo if valid else messagebox.showerror)(APP_NAME, message)

    def _import_cdf(self) -> None:
        self._import_network("cdf")

    def _import_cgmes(self) -> None:
        self._import_network("cgmes")

    def _import_network(self, kind: str) -> None:
        if not self._authorize(Permission.IMPORT_NETWORK):
            return
        if kind == "cdf":
            selected = filedialog.askopenfilename(title="Import IEEE CDF", filetypes=[("IEEE CDF", "*.cdf *.txt"), ("All files", "*.*")])
            importer = IEECDFImporter()
        else:
            selected = filedialog.askopenfilename(title="Import CIM/CGMES", filetypes=[("CGMES package", "*.zip *.xml *.rdf"), ("All files", "*.*")])
            importer = CIMCGMESImporter()
        if not selected:
            return
        try:
            report = importer.load(selected)
            self.import_report = report
            issue_text = "\n".join(f"[{item.severity}] {item.code}: {item.message}" for item in report.issues[:12]) or "No importer messages."
            if report.ready_for_analysis and messagebox.askyesno(APP_NAME, f"Import completed.\n\n{issue_text}\n\nReplace the active project with this imported network?"):
                self.network = report.model
                self.summary = self.ac_result = self.opf_result = None
                self.project_path = None
                self._record(f"import_{kind}", "success", Path(selected).name)
                self.status_var.set(f"Imported {Path(selected).name}; review provenance before analysis.")
                self._refresh_all()
            elif not report.ready_for_analysis:
                self._record(f"import_{kind}", "failed", Path(selected).name)
                messagebox.showerror(APP_NAME, f"Import did not produce an analyzable network.\n\n{issue_text}")
        except (OSError, ValidationError, ValueError) as exc:
            self._record(f"import_{kind}", "failed", str(exc))
            messagebox.showerror(APP_NAME, f"Import could not complete.\n\n{exc}")

    def _run_ac_power_flow(self) -> None:
        if not self._authorize(Permission.RUN_AC_POWER_FLOW):
            return
        try:
            self.config(cursor="watch")
            self.update_idletasks()
            self.ac_result = self.ac_engine.solve(self.network)
            self.opf_result = None
            brief = [
                "Balanced AC power flow completed.",
                f"Convergence: {self.ac_result.iterations} Newton iterations; maximum mismatch {self.ac_result.max_mismatch_mva:.6g} MVA.",
                f"Active losses: {self.ac_result.total_losses_mw:.3f} MW; reactive losses: {self.ac_result.total_losses_mvar:.3f} Mvar.",
                f"Maximum branch loading: {self.ac_result.max_loading_pct:.1f}%.",
                *self.ac_result.messages,
                "\nThis is balanced steady-state AC screening, not a protection, short-circuit or dynamic-stability study.",
            ]
            self._set_brief("\n".join(brief))
            self._draw_network()
            self._record("ac_power_flow", "success", f"iterations={self.ac_result.iterations}")
            self.status_var.set("AC power flow completed.")
        except (ValidationError, RuntimeError) as exc:
            self._record("ac_power_flow", "failed", str(exc))
            messagebox.showerror(APP_NAME, f"AC power flow could not complete.\n\n{exc}")
        finally:
            self.config(cursor="")

    def _run_operational_optimization(self) -> None:
        if not self._authorize(Permission.RUN_OPTIMIZATION):
            return
        try:
            self.config(cursor="watch")
            self.update_idletasks()
            self.opf_result = self.dispatch_engine.optimize_and_validate(self.network, self.ac_engine)
            self.ac_result = self.opf_result.ac_power_flow
            dispatch = self.opf_result.dispatch
            brief = [
                "Constrained economic dispatch with AC feasibility post-check completed.",
                f"Dispatch objective: {dispatch.objective_cost_per_hour:.3f} cost-units/hour; dispatched demand: {dispatch.dispatched_mw:.3f} MW.",
                f"Economic dispatch feasible: {'yes' if dispatch.feasible else 'no'}; AC post-check feasible: {'yes' if self.opf_result.feasible_after_ac_check else 'no'}.",
                "\nThis procedure is not a certified nonlinear AC-OPF. Review all constraints and violations before using its setpoints.",
                *self.opf_result.violations,
            ]
            self._set_brief("\n".join(brief))
            self._draw_network()
            self._record("economic_dispatch_ac_check", "success" if self.opf_result.feasible_after_ac_check else "warning", f"objective={dispatch.objective_cost_per_hour:.3f}")
            self.status_var.set("Economic dispatch and AC feasibility check completed.")
        except (ValidationError, RuntimeError) as exc:
            self._record("economic_dispatch_ac_check", "failed", str(exc))
            messagebox.showerror(APP_NAME, f"Optimization could not complete.\n\n{exc}")
        finally:
            self.config(cursor="")

    def _new_sample(self) -> None:
        if not self._authorize(Permission.EDIT_PROJECT):
            return
        if not self._confirm_discard():
            return
        self.network = sample_network()
        self.summary = None
        self.project_path = None
        self._log("Created a fresh demonstration project.")
        self.status_var.set("Demonstration project loaded.")
        self._refresh_all()

    def _open_project(self) -> None:
        if not self._authorize(Permission.VIEW_PROJECT):
            return
        selected = filedialog.askopenfilename(title="Open Grid Resilience project", filetypes=[("Grid Resilience project", "*.json"), ("All files", "*.*")])
        if not selected:
            return
        try:
            self.network = ProjectStore.load(selected)
            self.summary = None
            self.project_path = Path(selected)
            self._log(f"Opened project: {self.project_path.name}")
            self.status_var.set(f"Opened {self.project_path.name}")
            self._refresh_all()
        except (OSError, ValidationError) as exc:
            messagebox.showerror(APP_NAME, f"Unable to open project.\n\n{exc}")

    def _save_project(self, force_dialog: bool = False) -> None:
        if not self._authorize(Permission.EDIT_PROJECT):
            return
        destination = self.project_path
        if force_dialog or destination is None:
            selected = filedialog.asksaveasfilename(title="Save Grid Resilience project", defaultextension=".json", initialfile="grid-resilience-project.json", filetypes=[("Grid Resilience project", "*.json")])
            if not selected:
                return
            destination = Path(selected)
        try:
            ProjectStore.save(destination, self.network)
            self.project_path = destination
            self._log(f"Saved project: {destination.name}")
            self.status_var.set(f"Saved {destination.name}")
        except (OSError, ValidationError) as exc:
            messagebox.showerror(APP_NAME, f"Unable to save project.\n\n{exc}")

    def _validate_model(self) -> None:
        if not self._authorize(Permission.VIEW_PROJECT):
            return
        issues = self.network.validate()
        self._refresh_quality()
        if issues:
            self._log("Validation failed: " + "; ".join(issues))
            messagebox.showerror(APP_NAME, "Model validation failed:\n\n" + "\n".join(f"• {item}" for item in issues))
            self.status_var.set("Validation failed; correct the model before analysis.")
        else:
            self._log("Model validation passed.")
            messagebox.showinfo(APP_NAME, "Model validation passed. The project is ready for deterministic N-1 DC screening.")
            self.status_var.set("Validation passed.")

    def _run_analysis(self) -> None:
        if not self._authorize(Permission.RUN_SCREENING):
            return
        try:
            self.network.require_valid()
            self.config(cursor="watch")
            self.update_idletasks()
            self.summary = self.engine.analyse(self.network)
            self._populate_contingencies()
            self._refresh_summary()
            self._draw_network()
            self._log(f"Ran N-1 screening: {len(self.summary.contingencies)} scenarios; index {self.summary.resilience_index:.1f}.")
            self.status_var.set(f"Analysis completed: resilience index {self.summary.resilience_index:.1f}/100")
        except (ValidationError, RuntimeError) as exc:
            messagebox.showerror(APP_NAME, f"Analysis could not complete.\n\n{exc}")
            self.status_var.set("Analysis failed.")
        finally:
            self.config(cursor="")

    def _populate_contingencies(self) -> None:
        for item in self.contingency_tree.get_children():
            self.contingency_tree.delete(item)
        if self.summary is None:
            return
        for rank, result in enumerate(self.summary.ranked, start=1):
            tag = result.status.value
            max_loading = "—" if result.max_loading_pct is None else f"{result.max_loading_pct:.1f}%"
            self.contingency_tree.insert("", "end", values=(rank, result.status.value.title(), f"{result.id} · {result.element_name}", f"{result.severity_score:.1f}", max_loading, f"{result.unserved_load_mw:.1f}", result.message), tags=(tag,))

    def _export_csv(self) -> None:
        if not self._authorize(Permission.EXPORT_RESULTS):
            return
        if self.summary is None:
            messagebox.showwarning(APP_NAME, "Run N-1 screening before exporting a ranked contingency queue.")
            return
        selected = filedialog.asksaveasfilename(title="Export ranked contingency queue", defaultextension=".csv", initialfile="grid-resilience-contingencies.csv", filetypes=[("CSV", "*.csv")])
        if not selected:
            return
        try:
            export_results_csv(self.summary, selected)
            self._log(f"Exported contingency CSV: {Path(selected).name}")
            self.status_var.set(f"Exported {Path(selected).name}")
            messagebox.showinfo(APP_NAME, "Ranked contingency queue exported successfully.")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Unable to export CSV.\n\n{exc}")

    def _export_html_report(self) -> None:
        self._export_engineering_report("html")

    def _export_pdf_report(self) -> None:
        self._export_engineering_report("pdf")

    def _export_engineering_report(self, kind: str) -> None:
        if not self._authorize(Permission.EXPORT_RESULTS):
            return
        if self.summary is None and self.n2_summary is None and self.transient_result is None:
            messagebox.showwarning(APP_NAME, "Run at least one engineering screening before exporting a report.")
            return
        extension = ".html" if kind == "html" else ".pdf"
        selected = filedialog.asksaveasfilename(title=f"Export {kind.upper()} engineering report", defaultextension=extension, initialfile=f"grid-resilience-engineering-report{extension}", filetypes=[(kind.upper(), f"*{extension}")])
        if not selected:
            return
        try:
            exporter = export_html_report if kind == "html" else export_pdf_report
            exporter(selected, self.network, self.summary, self.n2_summary, self.transient_result)
            self._record(f"export_{kind}_report", "success", Path(selected).name)
            self.status_var.set(f"Exported {Path(selected).name}")
            messagebox.showinfo(APP_NAME, f"{kind.upper()} engineering report exported successfully.")
        except (OSError, RuntimeError) as exc:
            self._record(f"export_{kind}_report", "failed", str(exc))
            messagebox.showerror(APP_NAME, f"Unable to export {kind.upper()} report.\n\n{exc}")

    def _edit_model(self) -> None:
        if not self._authorize(Permission.EDIT_PROJECT):
            return
        dialog = tk.Toplevel(self)
        dialog.title("Edit model data")
        dialog.geometry("900x700")
        dialog.configure(bg=COLORS["surface"])
        ttk.Label(dialog, text="Project data editor", style="Section.TLabel").pack(anchor="w", padx=16, pady=(16, 2))
        ttk.Label(dialog, text="Edit the versioned JSON model. Changes are validated before they replace the active project.", foreground=COLORS["muted"]).pack(anchor="w", padx=16, pady=(0, 10))
        editor = tk.Text(dialog, wrap="none", font=("Cascadia Mono", 9), bg="#FBFDFF", fg=COLORS["ink"], relief="solid", bd=1, padx=10, pady=10)
        editor.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        editor.insert("1.0", json.dumps(self.network.to_dict(), indent=2, sort_keys=True))
        controls = ttk.Frame(dialog, padding=(16, 0, 16, 16))
        controls.pack(fill="x")
        def apply() -> None:
            try:
                candidate = NetworkModel.from_dict(json.loads(editor.get("1.0", "end")))
                candidate.require_valid()
                self.network = candidate
                self.summary = None
                self._log("Applied validated model edits.")
                self.status_var.set("Validated model edits applied; rerun analysis.")
                self._refresh_all()
                dialog.destroy()
            except (json.JSONDecodeError, ValidationError) as exc:
                messagebox.showerror("Invalid model", str(exc), parent=dialog)
        ttk.Button(controls, text="Cancel", command=dialog.destroy, style="Secondary.TButton").pack(side="right")
        ttk.Button(controls, text="Validate and apply", command=apply, style="Primary.TButton").pack(side="right", padx=(0, 8))

    def _show_audit(self) -> None:
        if not self._authorize(Permission.VIEW_AUDIT):
            return
        persisted = [f"{entry.timestamp} — {entry.actor} — {entry.action}: {entry.outcome} {entry.detail}" for entry in self.audit_log.entries(40)]
        messagebox.showinfo("Audit trail", "\n".join(persisted or self.audit[-40:]) if (persisted or self.audit) else "No events recorded.")

    def _show_methodology(self) -> None:
        messagebox.showinfo("Methodology and limitations", "This release provides deterministic DC N-1 screening, balanced Newton–Raphson AC power flow, and quadratic-cost economic dispatch with an AC feasibility post-check. The dispatch feature is not a certified nonlinear AC-OPF; CDF inputs may contain inferred operational/economic data; and the CIM/CGMES adapter is a documented subset importer rather than a conformity claim. It does not calculate protection coordination, short circuit, unbalanced networks or dynamic stability. Independently validate all inputs and use approved engineering studies before operational decisions.")

    def _confirm_discard(self) -> bool:
        return messagebox.askyesno(APP_NAME, "Create a new demonstration project? Any unsaved local changes will be discarded.")

    def _log(self, event: str) -> None:
        from datetime import datetime, timezone
        self.audit.append(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC — {event}")


def main() -> None:
    app = GridResilienceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
