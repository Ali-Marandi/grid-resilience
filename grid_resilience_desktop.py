"""Desktop application for Grid Resilience Studio."""
from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from grid_resilience import (
    AnalysisSummary,
    NetworkModel,
    ProjectStore,
    ResilienceEngine,
    ResultStatus,
    ValidationError,
    export_results_csv,
    sample_network,
)

APP_NAME = "Grid Resilience Studio"
APP_VERSION = "1.0.0"

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
        self.network: NetworkModel = sample_network()
        self.summary: AnalysisSummary | None = None
        self.project_path: Path | None = None
        self.audit: list[str] = []
        self._configure_style()
        self._build_menu()
        self._build_layout()
        self._log("Application started with the validated demonstration project.")
        self._refresh_all()

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

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        project = tk.Menu(menu, tearoff=False)
        project.add_command(label="New demonstration project", command=self._new_sample)
        project.add_command(label="Open project…", command=self._open_project)
        project.add_command(label="Save project", command=self._save_project)
        project.add_command(label="Save project as…", command=lambda: self._save_project(force_dialog=True))
        project.add_separator()
        project.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="Project", menu=project)
        analysis = tk.Menu(menu, tearoff=False)
        analysis.add_command(label="Validate model", command=self._validate_model)
        analysis.add_command(label="Run N-1 screening", command=self._run_analysis)
        analysis.add_command(label="Export contingency CSV…", command=self._export_csv)
        menu.add_cascade(label="Analysis", menu=analysis)
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
        self._side_button(side, "Validate model", self._validate_model)
        self._side_button(side, "Edit model data", self._edit_model)
        self._side_button(side, "Open project", self._open_project)
        self._side_button(side, "Save project", self._save_project)
        ttk.Separator(side).pack(fill="x", pady=16)
        ttk.Label(side, text="GOVERNANCE", style="Section.TLabel").pack(anchor="w")
        ttk.Label(side, text="Every analysis run records the engine version, timestamp and screening outcomes in this session.", style="Panel.TLabel", foreground=COLORS["muted"], wraplength=205).pack(anchor="w", pady=(5, 12))
        self._side_button(side, "Export ranked CSV", self._export_csv)
        self._side_button(side, "View audit trail", self._show_audit)
        ttk.Separator(side).pack(fill="x", pady=16)
        tk.Label(side, text="ENGINEERING SCREENING ONLY", bg="#FFF4E5", fg="#8C4D00", font=("Segoe UI Semibold", 8), padx=8, pady=6).pack(anchor="w", fill="x")
        ttk.Label(side, text="DC power flow does not replace approved AC, protection or dynamic studies.", style="Panel.TLabel", foreground=COLORS["muted"], wraplength=205).pack(anchor="w", pady=(8, 0))

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
        notebook.add(overview, text="Network overview")
        notebook.add(contingencies, text="Contingency queue")
        notebook.add(data_quality, text="Model quality")
        self._build_overview(overview)
        self._build_contingencies(contingencies)
        self._build_data_quality(data_quality)

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
        flow_map = {flow.branch_id: flow for flow in self.summary.base_case.branch_flows} if self.summary else {}
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
            caption = f"{branch.id}\n{loading:.0f}%" if self.summary else branch.id
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

    def _new_sample(self) -> None:
        if not self._confirm_discard():
            return
        self.network = sample_network()
        self.summary = None
        self.project_path = None
        self._log("Created a fresh demonstration project.")
        self.status_var.set("Demonstration project loaded.")
        self._refresh_all()

    def _open_project(self) -> None:
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

    def _edit_model(self) -> None:
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
        messagebox.showinfo("Session audit trail", "\n".join(self.audit[-40:]) if self.audit else "No events recorded.")

    def _show_methodology(self) -> None:
        messagebox.showinfo("Methodology and limitations", "This release applies deterministic balanced DC power-flow screening to base and single-element outage scenarios. It evaluates topology, line thermal limits and estimated unserved load after islanding. It does not calculate AC voltage, reactive power, protection coordination, short circuit or dynamic stability. Independently validate all inputs and use approved engineering studies before operational decisions.")

    def _confirm_discard(self) -> bool:
        return messagebox.askyesno(APP_NAME, "Create a new demonstration project? Any unsaved local changes will be discarded.")

    def _log(self, event: str) -> None:
        from datetime import UTC, datetime
        self.audit.append(f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC — {event}")


def main() -> None:
    app = GridResilienceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
