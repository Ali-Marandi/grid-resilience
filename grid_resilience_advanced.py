"""N-2 contingency and cascading-overload screening for engineering review."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from grid_resilience import AnalysisError, Branch, Generator, NetworkModel, ResilienceEngine, ResultStatus


@dataclass(frozen=True)
class CascadeStep:
    sequence: int
    outaged_branch_id: str
    trigger_loading_pct: float
    message: str


@dataclass(frozen=True)
class N2ContingencyResult:
    id: str
    outaged_branch_ids: list[str]
    outaged_generator_ids: list[str]
    status: ResultStatus
    severity_score: float
    max_loading_pct: float | None
    overloaded_branch_ids: list[str]
    unserved_load_mw: float
    cascade_steps: list[CascadeStep]
    remedial_actions: list[str]
    message: str


@dataclass(frozen=True)
class N2AnalysisSummary:
    network_name: str
    results: list[N2ContingencyResult]

    @property
    def ranked(self) -> list[N2ContingencyResult]:
        return sorted(self.results, key=lambda item: (-item.severity_score, item.id))


class AdvancedContingencyEngine:
    """Deterministic N-2 and overload-cascade screening without control actions."""

    def __init__(self, cascade_trigger_loading_pct: float = 115.0, max_cascade_steps: int = 4) -> None:
        self.cascade_trigger_loading_pct = cascade_trigger_loading_pct
        self.max_cascade_steps = max_cascade_steps
        self._engine = ResilienceEngine()

    def analyse_n2(
        self,
        network: NetworkModel,
        include_generator_pairs: bool = False,
    ) -> N2AnalysisSummary:
        network.require_valid()
        elements: list[tuple[str, str]] = [("branch", item.id) for item in network.branches if item.in_service]
        if include_generator_pairs:
            elements.extend(("generator", item.id) for item in network.generators if item.in_service)
        results = [self._evaluate_pair(network, pair) for pair in combinations(elements, 2)]
        return N2AnalysisSummary(network_name=network.name, results=results)

    def _evaluate_pair(self, network: NetworkModel, pair: tuple[tuple[str, str], tuple[str, str]]) -> N2ContingencyResult:
        branch_ids = sorted(element_id for kind, element_id in pair if kind == "branch")
        generator_ids = sorted(element_id for kind, element_id in pair if kind == "generator")
        identifier = "N2-" + "-".join([*branch_ids, *generator_ids])
        try:
            solved = self._engine.solve_base_case(network, branch_ids, generator_ids)
        except AnalysisError as exc:
            unserved = self._unserved_if_islanded(network, branch_ids)
            return N2ContingencyResult(
                id=identifier,
                outaged_branch_ids=branch_ids,
                outaged_generator_ids=generator_ids,
                status=ResultStatus.ISLANDED if unserved else ResultStatus.UNSOLVED,
                severity_score=100.0,
                max_loading_pct=None,
                overloaded_branch_ids=[],
                unserved_load_mw=unserved,
                cascade_steps=[],
                remedial_actions=self._actions(ResultStatus.ISLANDED if unserved else ResultStatus.UNSOLVED, [], unserved),
                message=str(exc),
            )
        overloaded = [flow.branch_id for flow in solved.branch_flows if flow.loading_pct > 100.0]
        cascade = self._cascade(network, branch_ids, generator_ids)
        cascade_outages = {step.outaged_branch_id for step in cascade}
        combined_overloads = sorted(set(overloaded) | cascade_outages)
        status = ResultStatus.VIOLATION if combined_overloads else ResultStatus.SECURE
        severity = max(0.0, solved.max_loading_pct - 85.0) * 0.6
        severity += sum(max(0.0, flow.loading_pct - 100.0) for flow in solved.branch_flows)
        severity += len(cascade) * 18.0
        severity = min(100.0, round(severity, 2))
        return N2ContingencyResult(
            id=identifier,
            outaged_branch_ids=branch_ids,
            outaged_generator_ids=generator_ids,
            status=status,
            severity_score=severity,
            max_loading_pct=solved.max_loading_pct,
            overloaded_branch_ids=combined_overloads,
            unserved_load_mw=0.0,
            cascade_steps=cascade,
            remedial_actions=self._actions(status, combined_overloads, 0.0),
            message=("No N-2 thermal violation in DC screening" if status is ResultStatus.SECURE else "N-2 thermal or cascade screening violation"),
        )

    def _cascade(
        self,
        network: NetworkModel,
        initial_branches: Iterable[str],
        generator_ids: Iterable[str],
    ) -> list[CascadeStep]:
        outaged = set(initial_branches)
        steps: list[CascadeStep] = []
        for sequence in range(1, self.max_cascade_steps + 1):
            try:
                solved = self._engine.solve_base_case(network, outaged, generator_ids)
            except AnalysisError:
                break
            candidates = [flow for flow in solved.branch_flows if flow.loading_pct >= self.cascade_trigger_loading_pct]
            if not candidates:
                break
            trigger = max(candidates, key=lambda flow: (flow.loading_pct, flow.branch_id))
            outaged.add(trigger.branch_id)
            steps.append(CascadeStep(
                sequence=sequence,
                outaged_branch_id=trigger.branch_id,
                trigger_loading_pct=round(trigger.loading_pct, 3),
                message="Screening cascade removes the most overloaded branch; engineering review required",
            ))
        return steps

    def _unserved_if_islanded(self, network: NetworkModel, outaged_branch_ids: Iterable[str]) -> float:
        active = [item for item in network.branches if item.in_service and item.id not in set(outaged_branch_ids)]
        connected, islanded = self._engine._topology(network, active)
        if connected:
            return 0.0
        return round(sum(network.bus(bus_id).load_mw for bus_id in islanded), 3)

    @staticmethod
    def _actions(status: ResultStatus, overloaded: list[str], unserved: float) -> list[str]:
        if status is ResultStatus.ISLANDED:
            return [
                "Review islanding boundary and restoration options with the responsible system operator.",
                f"Validate the {unserved:.1f} MW screening estimate against approved load-shedding studies.",
            ]
        if status is ResultStatus.UNSOLVED:
            return ["Validate model connectivity, slack-source availability, and data quality before re-running the study."]
        if overloaded:
            return [
                "Review non-binding topology, dispatch, and demand-management alternatives in an approved engineering study.",
                "Do not apply a control action from this screening result without authorised operational review.",
            ]
        return ["No remedial action suggested by the DC screening; retain normal engineering review controls."]
