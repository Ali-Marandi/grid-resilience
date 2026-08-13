"""Reduced-order transient-stability screening for Grid Resilience Control Center.

This module uses an implicit trapezoidal step solved with Newton iterations.  It
models classical generator rotor-angle and speed deviations after a user-defined
fault application/clearing event.  It is intentionally a screening module: it
does not model excitation systems, governors, detailed protection, unbalanced
faults, EMT behaviour, or inverter controls.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable

from grid_resilience import AnalysisError, NetworkModel, ResilienceEngine


TRANSIENT_SCREENING_DISCLAIMER = (
    "Multi-generator stability results are reduced-order, balanced positive-sequence "
    "engineering screening only. They are not validated RMS/EMT studies and must not "
    "be the sole basis for protection or real-time operational decisions."
)


class StabilityStatus(str, Enum):
    STABLE = "stable"
    UNSTABLE = "unstable"
    NUMERICAL_LIMIT = "numerical_limit"


@dataclass(frozen=True)
class FaultEvent:
    id: str
    apply_time_s: float
    clear_time_s: float
    severity: float = 0.85
    post_fault_transfer_factor: float = 1.0
    description: str = "Three-phase fault screening event"

    def validate(self) -> None:
        if not self.id.strip():
            raise AnalysisError("fault event id cannot be empty")
        if self.apply_time_s < 0 or self.clear_time_s <= self.apply_time_s:
            raise AnalysisError("fault clearing time must be after fault application")
        if not 0.0 <= self.severity <= 1.0:
            raise AnalysisError("fault severity must be between 0 and 1")
        if not 0.0 < self.post_fault_transfer_factor <= 1.0:
            raise AnalysisError("post-fault transfer factor must be in (0, 1]")


@dataclass(frozen=True)
class GeneratorDynamicModel:
    generator_id: str
    bus_id: str
    inertia_h_s: float = 4.0
    damping_pu: float = 1.0

    def validate(self) -> None:
        if self.inertia_h_s <= 0:
            raise AnalysisError(f"generator {self.generator_id}: inertia must be positive")
        if self.damping_pu < 0:
            raise AnalysisError(f"generator {self.generator_id}: damping cannot be negative")


@dataclass(frozen=True)
class TransientPoint:
    time_s: float
    rotor_angles_deg: dict[str, float]
    speed_deviation_pu: dict[str, float]
    transfer_factor: float


@dataclass(frozen=True)
class TransientSimulationResult:
    fault_id: str
    status: StabilityStatus
    points: list[TransientPoint]
    max_angle_separation_deg: float
    max_speed_deviation_pu: float
    message: str
    disclaimer: str = TRANSIENT_SCREENING_DISCLAIMER


@dataclass(frozen=True)
class CriticalClearingTimeResult:
    fault_id: str
    critical_clearing_time_s: float
    lower_stable_bound_s: float
    upper_unstable_bound_s: float | None
    iterations: int
    disclaimer: str = TRANSIENT_SCREENING_DISCLAIMER


class TransientStabilityEngine:
    """Classical-model screening engine with an implicit Newton time integrator."""

    def __init__(
        self,
        time_step_s: float = 0.01,
        nominal_frequency_hz: float = 50.0,
        max_newton_iterations: int = 12,
        newton_tolerance: float = 1e-8,
    ) -> None:
        if time_step_s <= 0:
            raise ValueError("time_step_s must be positive")
        self.time_step_s = time_step_s
        self.omega_base = 2.0 * math.pi * nominal_frequency_hz
        self.max_newton_iterations = max_newton_iterations
        self.newton_tolerance = newton_tolerance

    def simulate(
        self,
        network: NetworkModel,
        fault: FaultEvent,
        duration_s: float = 5.0,
        dynamics: Iterable[GeneratorDynamicModel] | None = None,
        angle_limit_deg: float = 180.0,
        speed_limit_pu: float = 0.12,
    ) -> TransientSimulationResult:
        network.require_valid()
        fault.validate()
        if duration_s <= fault.clear_time_s:
            raise AnalysisError("duration must extend beyond the fault clearing event")
        models = self._models(network, dynamics)
        generator_ids = [model.generator_id for model in models]
        initial_angles = self._initial_angles(network, models)
        state = [value for generator_id in generator_ids for value in (initial_angles[generator_id], 0.0)]
        coupling = self._coupling(network, models)
        points: list[TransientPoint] = []
        status = StabilityStatus.STABLE
        message = "Screening simulation remained within configured angle and speed limits"
        steps = int(math.ceil(duration_s / self.time_step_s))
        time_s = 0.0

        for step in range(steps + 1):
            factor = self._transfer_factor(time_s, fault)
            points.append(self._point(time_s, state, generator_ids, factor))
            separation = self._angle_separation_deg(state)
            speed = max((abs(state[index]) for index in range(1, len(state), 2)), default=0.0)
            if separation > angle_limit_deg or speed > speed_limit_pu:
                status = StabilityStatus.UNSTABLE
                message = "Configured rotor-angle or rotor-speed screening limit exceeded"
                break
            if step == steps:
                break
            next_time = min(duration_s, time_s + self.time_step_s)
            next_factor = self._transfer_factor(next_time, fault)
            try:
                state = self._implicit_trapezoid_step(
                    state, next_time - time_s, models, initial_angles, coupling, factor, next_factor
                )
            except AnalysisError as exc:
                status = StabilityStatus.NUMERICAL_LIMIT
                message = f"Numerical screening limit: {exc}"
                break
            time_s = next_time

        max_angle = max((self._angle_separation_from_point(point) for point in points), default=0.0)
        max_speed = max(
            (abs(value) for point in points for value in point.speed_deviation_pu.values()), default=0.0
        )
        return TransientSimulationResult(
            fault_id=fault.id,
            status=status,
            points=points,
            max_angle_separation_deg=round(max_angle, 4),
            max_speed_deviation_pu=round(max_speed, 6),
            message=message,
        )

    def critical_clearing_time(
        self,
        network: NetworkModel,
        fault: FaultEvent,
        duration_s: float = 5.0,
        search_max_s: float = 1.0,
        iterations: int = 14,
    ) -> CriticalClearingTimeResult:
        fault.validate()
        if search_max_s <= fault.apply_time_s:
            raise AnalysisError("search_max_s must be later than fault application")
        lower = fault.apply_time_s
        upper = search_max_s
        stable_upper: float | None = None
        for _ in range(iterations):
            candidate = (lower + upper) / 2.0
            trial = FaultEvent(
                id=fault.id,
                apply_time_s=fault.apply_time_s,
                clear_time_s=candidate,
                severity=fault.severity,
                post_fault_transfer_factor=fault.post_fault_transfer_factor,
                description=fault.description,
            )
            result = self.simulate(network, trial, max(duration_s, candidate + 1.0))
            if result.status is StabilityStatus.STABLE:
                lower = candidate
                stable_upper = candidate
            else:
                upper = candidate
        return CriticalClearingTimeResult(
            fault_id=fault.id,
            critical_clearing_time_s=round(lower, 4),
            lower_stable_bound_s=round(lower, 4),
            upper_unstable_bound_s=None if stable_upper == search_max_s else round(upper, 4),
            iterations=iterations,
        )

    def _models(
        self, network: NetworkModel, supplied: Iterable[GeneratorDynamicModel] | None
    ) -> list[GeneratorDynamicModel]:
        online = [item for item in network.generators if item.in_service]
        if not online:
            raise AnalysisError("at least one online generator is required for transient screening")
        values = list(supplied) if supplied is not None else [
            GeneratorDynamicModel(generator_id=item.id, bus_id=item.bus_id) for item in online
        ]
        allowed = {item.id: item for item in online}
        if {item.generator_id for item in values} != set(allowed):
            raise AnalysisError("dynamic model list must contain exactly the online generators")
        for item in values:
            item.validate()
            if allowed[item.generator_id].bus_id != item.bus_id:
                raise AnalysisError(f"generator {item.generator_id}: dynamic model bus mismatch")
        return values

    def _initial_angles(self, network: NetworkModel, models: list[GeneratorDynamicModel]) -> dict[str, float]:
        solved = ResilienceEngine().solve_base_case(network)
        return {
            model.generator_id: math.radians(solved.angles_deg.get(model.bus_id, 0.0))
            for model in models
        }

    def _coupling(
        self, network: NetworkModel, models: list[GeneratorDynamicModel]
    ) -> dict[tuple[str, str], float]:
        values: dict[tuple[str, str], float] = {}
        for left_index, left in enumerate(models):
            for right in models[left_index + 1 :]:
                equivalent_x = self._shortest_reactance(network, left.bus_id, right.bus_id)
                if equivalent_x is not None:
                    values[(left.generator_id, right.generator_id)] = network.base_mva * 0.35 / max(equivalent_x, 0.05)
        return values

    @staticmethod
    def _shortest_reactance(network: NetworkModel, start: str, target: str) -> float | None:
        frontier: dict[str, float] = {start: 0.0}
        seen: set[str] = set()
        while frontier:
            node = min(frontier, key=frontier.get)
            cost = frontier.pop(node)
            if node == target:
                return cost
            if node in seen:
                continue
            seen.add(node)
            for branch in network.branches:
                if not branch.in_service:
                    continue
                neighbour = branch.to_bus if branch.from_bus == node else branch.from_bus if branch.to_bus == node else None
                if neighbour is None or neighbour in seen:
                    continue
                candidate = cost + branch.reactance_pu
                if candidate < frontier.get(neighbour, float("inf")):
                    frontier[neighbour] = candidate
        return None

    def _implicit_trapezoid_step(
        self,
        state: list[float],
        dt: float,
        models: list[GeneratorDynamicModel],
        initial_angles: dict[str, float],
        coupling: dict[tuple[str, str], float],
        factor_now: float,
        factor_next: float,
    ) -> list[float]:
        derivative_now = self._derivative(state, models, initial_angles, coupling, factor_now)
        candidate = [value + dt * rate for value, rate in zip(state, derivative_now)]
        for _ in range(self.max_newton_iterations):
            derivative_next = self._derivative(candidate, models, initial_angles, coupling, factor_next)
            residual = [
                candidate[index] - state[index] - dt * (derivative_now[index] + derivative_next[index]) / 2.0
                for index in range(len(state))
            ]
            if max((abs(value) for value in residual), default=0.0) < self.newton_tolerance:
                return candidate
            jacobian = self._numerical_jacobian(
                candidate, residual, state, dt, models, initial_angles, coupling, factor_now, factor_next, derivative_now
            )
            correction = _solve_linear(jacobian, [-value for value in residual])
            candidate = [value + delta for value, delta in zip(candidate, correction)]
            if max((abs(value) for value in correction), default=0.0) < self.newton_tolerance:
                return candidate
        raise AnalysisError("implicit Newton step did not converge")

    def _numerical_jacobian(
        self,
        candidate: list[float],
        residual: list[float],
        state: list[float],
        dt: float,
        models: list[GeneratorDynamicModel],
        initial_angles: dict[str, float],
        coupling: dict[tuple[str, str], float],
        factor_now: float,
        factor_next: float,
        derivative_now: list[float],
    ) -> list[list[float]]:
        size = len(candidate)
        jacobian = [[0.0 for _ in range(size)] for _ in range(size)]
        for column in range(size):
            delta = 1e-6 * max(1.0, abs(candidate[column]))
            perturbed = candidate[:]
            perturbed[column] += delta
            next_derivative = self._derivative(perturbed, models, initial_angles, coupling, factor_next)
            next_residual = [
                perturbed[index] - state[index] - dt * (derivative_now[index] + next_derivative[index]) / 2.0
                for index in range(size)
            ]
            for row in range(size):
                jacobian[row][column] = (next_residual[row] - residual[row]) / delta
        return jacobian

    def _derivative(
        self,
        state: list[float],
        models: list[GeneratorDynamicModel],
        initial_angles: dict[str, float],
        coupling: dict[tuple[str, str], float],
        transfer_factor: float,
    ) -> list[float]:
        angles = {model.generator_id: state[index * 2] for index, model in enumerate(models)}
        result: list[float] = []
        for index, model in enumerate(models):
            delta = state[index * 2]
            omega = state[index * 2 + 1]
            electrical_deviation = self._electrical_deviation(
                model.generator_id, angles, initial_angles, coupling, transfer_factor
            )
            reference_k = 0.10
            phase_offset = 0.35
            electrical_deviation += reference_k * (
                transfer_factor * math.sin(delta - initial_angles[model.generator_id] + phase_offset)
                - math.sin(phase_offset)
            )
            result.extend((self.omega_base * omega, (-electrical_deviation - model.damping_pu * omega) / (2.0 * model.inertia_h_s)))
        return result

    @staticmethod
    def _electrical_deviation(
        generator_id: str,
        angles: dict[str, float],
        initial: dict[str, float],
        coupling: dict[tuple[str, str], float],
        factor: float,
    ) -> float:
        value = 0.0
        for (left, right), coefficient in coupling.items():
            if generator_id == left:
                value += coefficient * (
                    factor * math.sin(angles[left] - angles[right]) - math.sin(initial[left] - initial[right])
                )
            elif generator_id == right:
                value += coefficient * (
                    factor * math.sin(angles[right] - angles[left]) - math.sin(initial[right] - initial[left])
                )
        return value

    @staticmethod
    def _transfer_factor(time_s: float, fault: FaultEvent) -> float:
        if fault.apply_time_s <= time_s < fault.clear_time_s:
            return max(0.01, 1.0 - fault.severity)
        if time_s >= fault.clear_time_s:
            return fault.post_fault_transfer_factor
        return 1.0

    @staticmethod
    def _point(time_s: float, state: list[float], generator_ids: list[str], factor: float) -> TransientPoint:
        return TransientPoint(
            time_s=round(time_s, 6),
            rotor_angles_deg={generator_id: round(math.degrees(state[index * 2]), 5) for index, generator_id in enumerate(generator_ids)},
            speed_deviation_pu={generator_id: round(state[index * 2 + 1], 8) for index, generator_id in enumerate(generator_ids)},
            transfer_factor=round(factor, 4),
        )

    @staticmethod
    def _angle_separation_deg(state: list[float]) -> float:
        angles = [math.degrees(state[index]) for index in range(0, len(state), 2)]
        return max(angles) - min(angles) if angles else 0.0

    @staticmethod
    def _angle_separation_from_point(point: TransientPoint) -> float:
        values = list(point.rotor_angles_deg.values())
        return max(values) - min(values) if values else 0.0


def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for pivot_col in range(size):
        pivot_row = max(range(pivot_col, size), key=lambda row: abs(augmented[row][pivot_col]))
        if abs(augmented[pivot_row][pivot_col]) < 1e-12:
            raise AnalysisError("transient Newton Jacobian is singular")
        augmented[pivot_col], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_col]
        pivot = augmented[pivot_col][pivot_col]
        augmented[pivot_col] = [value / pivot for value in augmented[pivot_col]]
        for row in range(size):
            if row == pivot_col:
                continue
            factor = augmented[row][pivot_col]
            augmented[row] = [value - factor * source for value, source in zip(augmented[row], augmented[pivot_col])]
    return [augmented[row][-1] for row in range(size)]
