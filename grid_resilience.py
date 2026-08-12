"""Grid Resilience Studio core engine.

A deterministic, dependency-free DC power-flow and N-1 contingency engine intended
for engineering screening and training.  It is not a substitute for operational
control-room studies, protection studies, or certified AC/dynamic simulations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
import csv
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

CORE_VERSION = "1.0.0"
SCHEMA_VERSION = "grid-resilience/1.0"


class ValidationError(ValueError):
    """Raised when a project model is internally inconsistent."""


class AnalysisError(RuntimeError):
    """Raised when a numerical analysis cannot be completed."""


class ContingencyKind(str, Enum):
    BRANCH = "branch"
    GENERATOR = "generator"


class ResultStatus(str, Enum):
    SECURE = "secure"
    VIOLATION = "violation"
    ISLANDED = "islanded"
    UNSOLVED = "unsolved"


@dataclass(frozen=True)
class Bus:
    id: str
    name: str
    voltage_kv: float
    load_mw: float = 0.0
    is_slack: bool = False
    x: float | None = None
    y: float | None = None
    zone: str = "Default"

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.id.strip():
            issues.append("bus id cannot be empty")
        if not self.name.strip():
            issues.append(f"bus {self.id}: name cannot be empty")
        if self.voltage_kv <= 0:
            issues.append(f"bus {self.id}: voltage_kv must be positive")
        if self.load_mw < 0:
            issues.append(f"bus {self.id}: load_mw cannot be negative")
        return issues


@dataclass(frozen=True)
class Branch:
    id: str
    name: str
    from_bus: str
    to_bus: str
    reactance_pu: float
    thermal_limit_mva: float
    in_service: bool = True
    kind: str = "line"
    owner: str = ""

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.id.strip():
            issues.append("branch id cannot be empty")
        if self.from_bus == self.to_bus:
            issues.append(f"branch {self.id}: endpoints must differ")
        if self.reactance_pu <= 0:
            issues.append(f"branch {self.id}: reactance_pu must be positive")
        if self.thermal_limit_mva <= 0:
            issues.append(f"branch {self.id}: thermal_limit_mva must be positive")
        return issues


@dataclass(frozen=True)
class Generator:
    id: str
    name: str
    bus_id: str
    p_mw: float
    p_max_mw: float
    in_service: bool = True
    dispatchable: bool = True
    fuel: str = "Other"

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.id.strip():
            issues.append("generator id cannot be empty")
        if self.p_mw < 0 or self.p_max_mw < 0:
            issues.append(f"generator {self.id}: power values cannot be negative")
        if self.p_mw > self.p_max_mw + 1e-9:
            issues.append(f"generator {self.id}: p_mw exceeds p_max_mw")
        return issues


@dataclass
class NetworkModel:
    name: str
    base_mva: float
    buses: list[Bus]
    branches: list[Branch]
    generators: list[Generator]
    description: str = ""
    tags: list[str] = field(default_factory=list)
    schema: str = SCHEMA_VERSION

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.name.strip():
            issues.append("network name cannot be empty")
        if self.base_mva <= 0:
            issues.append("base_mva must be positive")
        bus_ids = [bus.id for bus in self.buses]
        branch_ids = [branch.id for branch in self.branches]
        generator_ids = [generator.id for generator in self.generators]
        for label, values in (("bus", bus_ids), ("branch", branch_ids), ("generator", generator_ids)):
            duplicates = sorted({value for value in values if values.count(value) > 1})
            if duplicates:
                issues.append(f"duplicate {label} id(s): {', '.join(duplicates)}")
        for bus in self.buses:
            issues.extend(bus.validate())
        for branch in self.branches:
            issues.extend(branch.validate())
            if branch.from_bus not in bus_ids or branch.to_bus not in bus_ids:
                issues.append(f"branch {branch.id}: references an unknown bus")
        for generator in self.generators:
            issues.extend(generator.validate())
            if generator.bus_id not in bus_ids:
                issues.append(f"generator {generator.id}: references an unknown bus")
        if sum(bus.is_slack for bus in self.buses) != 1:
            issues.append("exactly one slack bus is required")
        if not self.branches:
            issues.append("at least one branch is required")
        return issues

    def require_valid(self) -> None:
        issues = self.validate()
        if issues:
            raise ValidationError("Model validation failed:\n- " + "\n- ".join(issues))

    @property
    def slack_bus_id(self) -> str:
        self.require_valid()
        return next(bus.id for bus in self.buses if bus.is_slack)

    def bus(self, bus_id: str) -> Bus:
        return next(bus for bus in self.buses if bus.id == bus_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "base_mva": self.base_mva,
            "description": self.description,
            "tags": self.tags,
            "buses": [asdict(item) for item in self.buses],
            "branches": [asdict(item) for item in self.branches],
            "generators": [asdict(item) for item in self.generators],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetworkModel":
        schema = data.get("schema", SCHEMA_VERSION)
        if schema != SCHEMA_VERSION:
            raise ValidationError(f"Unsupported project schema: {schema}")
        try:
            return cls(
                schema=schema,
                name=str(data["name"]),
                base_mva=float(data["base_mva"]),
                description=str(data.get("description", "")),
                tags=[str(tag) for tag in data.get("tags", [])],
                buses=[Bus(**item) for item in data.get("buses", [])],
                branches=[Branch(**item) for item in data.get("branches", [])],
                generators=[Generator(**item) for item in data.get("generators", [])],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid project payload: {exc}") from exc


@dataclass(frozen=True)
class BranchFlow:
    branch_id: str
    from_bus: str
    to_bus: str
    flow_mw: float
    loading_pct: float
    limit_mva: float


@dataclass(frozen=True)
class BaseCaseResult:
    angles_deg: dict[str, float]
    branch_flows: list[BranchFlow]
    slack_injection_mw: float
    max_loading_pct: float


@dataclass(frozen=True)
class ContingencyResult:
    id: str
    kind: ContingencyKind
    element_id: str
    element_name: str
    status: ResultStatus
    severity_score: float
    max_loading_pct: float | None
    overloaded_branch_ids: list[str]
    islanded_bus_ids: list[str]
    unserved_load_mw: float
    message: str


@dataclass(frozen=True)
class AnalysisSummary:
    analysed_at: str
    engine_version: str
    network_name: str
    base_case: BaseCaseResult
    contingencies: list[ContingencyResult]
    resilience_index: float
    secure_count: int
    violation_count: int
    islanded_count: int
    unsolved_count: int

    @property
    def ranked(self) -> list[ContingencyResult]:
        return sorted(self.contingencies, key=lambda item: (-item.severity_score, item.id))


class ProjectStore:
    """Atomic JSON persistence with a small audit envelope for local projects."""

    @staticmethod
    def save(path: str | Path, network: NetworkModel) -> None:
        network.require_valid()
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now(UTC).isoformat(),
            "engine_version": CORE_VERSION,
            "project": network.to_dict(),
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=destination.parent, suffix=".tmp") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, destination)

    @staticmethod
    def load(path: str | Path) -> NetworkModel:
        try:
            with Path(path).open(encoding="utf-8") as handle:
                payload = json.load(handle)
            return NetworkModel.from_dict(payload["project"])
        except FileNotFoundError:
            raise
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValidationError(f"Could not read project: {exc}") from exc


class ResilienceEngine:
    """Deterministic DC screening engine with explicit topology and limit checks."""

    def analyse(self, network: NetworkModel, include_generator_outages: bool = True) -> AnalysisSummary:
        network.require_valid()
        base_case = self.solve_base_case(network)
        contingencies: list[ContingencyResult] = []
        for branch in (item for item in network.branches if item.in_service):
            contingencies.append(self._evaluate_branch_outage(network, branch))
        if include_generator_outages:
            for generator in (item for item in network.generators if item.in_service):
                contingencies.append(self._evaluate_generator_outage(network, generator))
        secure = sum(result.status is ResultStatus.SECURE for result in contingencies)
        violations = sum(result.status is ResultStatus.VIOLATION for result in contingencies)
        islanded = sum(result.status is ResultStatus.ISLANDED for result in contingencies)
        unsolved = sum(result.status is ResultStatus.UNSOLVED for result in contingencies)
        total = len(contingencies)
        weighted_penalty = sum(min(100.0, result.severity_score) for result in contingencies)
        resilience_index = 100.0 if total == 0 else max(0.0, round(100.0 - weighted_penalty / total, 2))
        return AnalysisSummary(
            analysed_at=datetime.now(UTC).isoformat(),
            engine_version=CORE_VERSION,
            network_name=network.name,
            base_case=base_case,
            contingencies=contingencies,
            resilience_index=resilience_index,
            secure_count=secure,
            violation_count=violations,
            islanded_count=islanded,
            unsolved_count=unsolved,
        )

    def solve_base_case(
        self,
        network: NetworkModel,
        outaged_branch_ids: Iterable[str] = (),
        outaged_generator_ids: Iterable[str] = (),
    ) -> BaseCaseResult:
        network.require_valid()
        branch_outages = set(outaged_branch_ids)
        generator_outages = set(outaged_generator_ids)
        active_branches = [item for item in network.branches if item.in_service and item.id not in branch_outages]
        if not active_branches:
            raise AnalysisError("No in-service branches remain")
        connected, islanded = self._topology(network, active_branches)
        if not connected:
            raise AnalysisError(f"Network is islanded: {', '.join(sorted(islanded))}")
        slack_id = network.slack_bus_id
        online_generators = [item for item in network.generators if item.in_service and item.id not in generator_outages]
        if not any(item.bus_id == slack_id for item in online_generators):
            raise AnalysisError("No online generator is connected to the slack bus")
        buses = [item.id for item in network.buses]
        index = {bus_id: offset for offset, bus_id in enumerate(buses)}
        slack_index = index[slack_id]
        p_mw = {bus.id: -bus.load_mw for bus in network.buses}
        for generator in online_generators:
            p_mw[generator.bus_id] += generator.p_mw
        p_without_slack = sum(value for bus_id, value in p_mw.items() if bus_id != slack_id)
        p_mw[slack_id] = -p_without_slack
        non_slack = [bus_id for bus_id in buses if bus_id != slack_id]
        reduced = [[0.0 for _ in non_slack] for _ in non_slack]
        vector = [p_mw[bus_id] / network.base_mva for bus_id in non_slack]
        reduced_index = {bus_id: offset for offset, bus_id in enumerate(non_slack)}
        for branch in active_branches:
            susceptance = 1.0 / branch.reactance_pu
            for first, second, sign in ((branch.from_bus, branch.from_bus, 1.0), (branch.to_bus, branch.to_bus, 1.0), (branch.from_bus, branch.to_bus, -1.0), (branch.to_bus, branch.from_bus, -1.0)):
                if first != slack_id and second != slack_id:
                    reduced[reduced_index[first]][reduced_index[second]] += sign * susceptance
        solution = self._solve_linear(reduced, vector)
        angle_rad = {slack_id: 0.0}
        angle_rad.update({bus_id: solution[offset] for offset, bus_id in enumerate(non_slack)})
        flows: list[BranchFlow] = []
        for branch in active_branches:
            flow = (angle_rad[branch.from_bus] - angle_rad[branch.to_bus]) / branch.reactance_pu * network.base_mva
            loading = abs(flow) / branch.thermal_limit_mva * 100.0
            flows.append(BranchFlow(branch.id, branch.from_bus, branch.to_bus, round(flow, 4), round(loading, 3), branch.thermal_limit_mva))
        max_loading = max((flow.loading_pct for flow in flows), default=0.0)
        return BaseCaseResult(
            angles_deg={bus_id: round(math.degrees(value), 5) for bus_id, value in angle_rad.items()},
            branch_flows=flows,
            slack_injection_mw=round(p_mw[slack_id], 4),
            max_loading_pct=round(max_loading, 3),
        )

    def _evaluate_branch_outage(self, network: NetworkModel, branch: Branch) -> ContingencyResult:
        active = [item for item in network.branches if item.in_service and item.id != branch.id]
        connected, islanded = self._topology(network, active)
        if not connected:
            unserved = round(sum(network.bus(bus_id).load_mw for bus_id in islanded), 3)
            severity = min(100.0, 70.0 + 25.0 * (unserved / max(1.0, sum(bus.load_mw for bus in network.buses))))
            return ContingencyResult(f"BR-{branch.id}", ContingencyKind.BRANCH, branch.id, branch.name, ResultStatus.ISLANDED, round(severity, 2), None, [], sorted(islanded), unserved, "Outage separates load from the slack-connected island")
        return self._assess_solved_case(network, ContingencyKind.BRANCH, branch.id, branch.name, [branch.id], [])

    def _evaluate_generator_outage(self, network: NetworkModel, generator: Generator) -> ContingencyResult:
        return self._assess_solved_case(network, ContingencyKind.GENERATOR, generator.id, generator.name, [], [generator.id])

    def _assess_solved_case(
        self,
        network: NetworkModel,
        kind: ContingencyKind,
        element_id: str,
        name: str,
        branches: list[str],
        generators: list[str],
    ) -> ContingencyResult:
        prefix = "BR" if kind is ContingencyKind.BRANCH else "GEN"
        try:
            result = self.solve_base_case(network, branches, generators)
        except AnalysisError as exc:
            return ContingencyResult(f"{prefix}-{element_id}", kind, element_id, name, ResultStatus.UNSOLVED, 100.0, None, [], [], 0.0, str(exc))
        overloaded = [flow.branch_id for flow in result.branch_flows if flow.loading_pct > 100.0 + 1e-9]
        if overloaded:
            severity = sum(max(0.0, flow.loading_pct - 100.0) for flow in result.branch_flows)
            severity = min(100.0, 35.0 + severity)
            message = f"{len(overloaded)} branch limit violation(s)"
            status = ResultStatus.VIOLATION
        else:
            severity = max(0.0, result.max_loading_pct - 85.0) * 0.5
            message = "No thermal limit violations in DC screening"
            status = ResultStatus.SECURE
        return ContingencyResult(
            f"{prefix}-{element_id}", kind, element_id, name, status, round(severity, 2), result.max_loading_pct,
            overloaded, [], 0.0, message,
        )

    @staticmethod
    def _topology(network: NetworkModel, branches: list[Branch]) -> tuple[bool, set[str]]:
        adjacency = {bus.id: set() for bus in network.buses}
        for branch in branches:
            adjacency[branch.from_bus].add(branch.to_bus)
            adjacency[branch.to_bus].add(branch.from_bus)
        seen: set[str] = set()
        stack = [network.slack_bus_id]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(adjacency[node] - seen)
        return len(seen) == len(adjacency), set(adjacency) - seen

    @staticmethod
    def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
        size = len(vector)
        if size == 0:
            return []
        augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
        for pivot_col in range(size):
            pivot_row = max(range(pivot_col, size), key=lambda row: abs(augmented[row][pivot_col]))
            if abs(augmented[pivot_row][pivot_col]) < 1e-12:
                raise AnalysisError("DC power flow matrix is singular")
            augmented[pivot_col], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_col]
            pivot = augmented[pivot_col][pivot_col]
            augmented[pivot_col] = [value / pivot for value in augmented[pivot_col]]
            for row in range(size):
                if row == pivot_col:
                    continue
                factor = augmented[row][pivot_col]
                augmented[row] = [value - factor * reference for value, reference in zip(augmented[row], augmented[pivot_col])]
        return [augmented[row][-1] for row in range(size)]


def export_results_csv(summary: AnalysisSummary, path: str | Path) -> None:
    """Export ranked contingency results for engineering review and traceability."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "rank", "id", "kind", "element_id", "element_name", "status", "severity_score",
            "max_loading_pct", "overloaded_branch_ids", "islanded_bus_ids", "unserved_load_mw", "message",
        ])
        writer.writeheader()
        for rank, item in enumerate(summary.ranked, start=1):
            writer.writerow({
                "rank": rank, "id": item.id, "kind": item.kind.value, "element_id": item.element_id,
                "element_name": item.element_name, "status": item.status.value, "severity_score": item.severity_score,
                "max_loading_pct": item.max_loading_pct, "overloaded_branch_ids": ";".join(item.overloaded_branch_ids),
                "islanded_bus_ids": ";".join(item.islanded_bus_ids), "unserved_load_mw": item.unserved_load_mw,
                "message": item.message,
            })


def sample_network() -> NetworkModel:
    """A validated five-bus sample project used in the first-run experience and tests."""
    return NetworkModel(
        name="North District Demonstrator",
        description="Illustrative DC screening model. Do not use for operational decisions.",
        base_mva=100.0,
        tags=["demo", "n-1", "training"],
        buses=[
            Bus("B1", "Central Generation", 230.0, is_slack=True, x=100, y=100),
            Bus("B2", "North Substation", 230.0, load_mw=45.0, x=310, y=60),
            Bus("B3", "Industrial Load", 230.0, load_mw=55.0, x=390, y=190),
            Bus("B4", "East Solar", 230.0, load_mw=25.0, x=250, y=320),
            Bus("B5", "South Load", 230.0, load_mw=35.0, x=80, y=290),
        ],
        branches=[
            Branch("L1", "Central–North", "B1", "B2", 0.12, 85.0),
            Branch("L2", "North–Industrial", "B2", "B3", 0.08, 70.0),
            Branch("L3", "Industrial–East", "B3", "B4", 0.10, 65.0),
            Branch("L4", "East–South", "B4", "B5", 0.07, 75.0),
            Branch("L5", "South–Central", "B5", "B1", 0.11, 85.0),
            Branch("L6", "North–East Tie", "B2", "B4", 0.16, 45.0),
        ],
        generators=[
            Generator("G1", "Central Thermal", "B1", 140.0, 220.0, fuel="Gas"),
            Generator("G2", "East Solar Park", "B4", 25.0, 50.0, fuel="Solar"),
        ],
    )


# Compatibility API retained from the original lightweight package.
def is_connected(nodes: set[str], edges: list[tuple[str, str]], removed: int | None = None) -> bool:
    if not nodes:
        return True
    adjacency = {node: set() for node in nodes}
    for index, (left, right) in enumerate(edges):
        if index == removed:
            continue
        if left not in nodes or right not in nodes:
            raise ValueError("edge references an unknown node")
        adjacency[left].add(right)
        adjacency[right].add(left)
    seen, stack = set(), [next(iter(nodes))]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node] - seen)
    return seen == nodes


def critical_lines(nodes: set[str], edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [edge for index, edge in enumerate(edges) if not is_connected(nodes, edges, index)]


def n_minus_one_secure(nodes: set[str], edges: list[tuple[str, str]]) -> bool:
    return is_connected(nodes, edges) and not critical_lines(nodes, edges)
