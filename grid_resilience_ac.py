"""Balanced AC power flow and constrained economic dispatch for Grid Resilience Studio.

The module is dependency-free and intentionally exposes convergence, residuals and
constraint exceptions.  It is designed for engineering screening and education; it
is not a replacement for a validated production-grade nonlinear AC-OPF solver.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import cmath
import math
from typing import Iterable

from grid_resilience import AnalysisError, Generator, NetworkModel, ValidationError


@dataclass(frozen=True)
class ACBusResult:
    bus_id: str
    bus_type: str
    voltage_pu: float
    angle_deg: float
    p_injection_mw: float
    q_injection_mvar: float
    voltage_violation: bool


@dataclass(frozen=True)
class ACBranchFlow:
    branch_id: str
    from_bus: str
    to_bus: str
    p_from_mw: float
    q_from_mvar: float
    p_to_mw: float
    q_to_mvar: float
    mva_from: float
    mva_to: float
    thermal_limit_mva: float
    loading_pct: float


@dataclass(frozen=True)
class ACPowerFlowResult:
    converged: bool
    iterations: int
    max_mismatch_mva: float
    buses: list[ACBusResult]
    branches: list[ACBranchFlow]
    total_losses_mw: float
    total_losses_mvar: float
    slack_p_mw: float
    slack_q_mvar: float
    messages: list[str]

    @property
    def max_loading_pct(self) -> float:
        return max((item.loading_pct for item in self.branches), default=0.0)


@dataclass(frozen=True)
class GeneratorDispatch:
    generator_id: str
    p_mw: float
    p_min_mw: float
    p_max_mw: float
    marginal_cost: float


@dataclass(frozen=True)
class EconomicDispatchResult:
    feasible: bool
    requested_mw: float
    dispatched_mw: float
    objective_cost_per_hour: float
    marginal_cost: float | None
    generators: list[GeneratorDispatch]
    messages: list[str]


@dataclass(frozen=True)
class OperationalOptimizationResult:
    """Constrained economic dispatch with an AC feasibility post-check.

    This is deliberately not labelled AC-OPF: dispatch is convex economic dispatch,
    followed by an AC power-flow validation.  A nonlinear AC-OPF solver is required
    for certified globally/locally optimal AC setpoints.
    """

    dispatch: EconomicDispatchResult
    ac_power_flow: ACPowerFlowResult | None
    feasible_after_ac_check: bool
    violations: list[str]


def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a dense linear system using partial-pivot Gaussian elimination."""
    size = len(vector)
    if size == 0:
        return []
    augmented = [row[:] + [vector[row_index]] for row_index, row in enumerate(matrix)]
    for pivot_col in range(size):
        pivot_row = max(range(pivot_col, size), key=lambda row: abs(augmented[row][pivot_col]))
        if abs(augmented[pivot_row][pivot_col]) < 1e-12:
            raise AnalysisError("AC Newton Jacobian is singular")
        augmented[pivot_col], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_col]
        pivot = augmented[pivot_col][pivot_col]
        augmented[pivot_col] = [value / pivot for value in augmented[pivot_col]]
        for row in range(size):
            if row == pivot_col:
                continue
            factor = augmented[row][pivot_col]
            augmented[row] = [value - factor * reference for value, reference in zip(augmented[row], augmented[pivot_col])]
    return [augmented[row][-1] for row in range(size)]


class ACPowerFlowEngine:
    """Newton-Raphson balanced AC power-flow engine with PV-to-PQ Q-limit switching."""

    def solve(
        self,
        network: NetworkModel,
        *,
        max_iterations: int = 30,
        tolerance_mva: float = 1e-5,
    ) -> ACPowerFlowResult:
        network.require_valid()
        if len(network.buses) < 2:
            raise ValidationError("AC power flow requires at least two buses")
        if max_iterations < 1 or tolerance_mva <= 0:
            raise ValidationError("max_iterations and tolerance_mva must be positive")

        buses = network.buses
        index = {bus.id: offset for offset, bus in enumerate(buses)}
        slack = index[network.slack_bus_id]
        active_branches = [branch for branch in network.branches if branch.in_service]
        if not active_branches:
            raise AnalysisError("No in-service branches remain")
        self._assert_connected(network, active_branches)
        ybus = self._ybus(network, active_branches, index)
        online = [generator for generator in network.generators if generator.in_service]
        if not any(generator.bus_id == buses[slack].id for generator in online):
            raise AnalysisError("No online generator is connected to the slack bus")

        p_spec, q_spec = self._specified_injections(network, online, index)
        roles = self._bus_roles(network, online, index, slack)
        messages: list[str] = []
        last_result: tuple[list[complex], list[float], list[float], int, float] | None = None

        # Each Q-limit conversion turns one PV bus into PQ, so the outer loop is bounded.
        for _ in range(len(buses) + 1):
            voltages, calculated_p, calculated_q, iterations, mismatch = self._newton_solve(
                ybus, p_spec, q_spec, roles, buses, slack, network.base_mva, max_iterations, tolerance_mva
            )
            last_result = (voltages, calculated_p, calculated_q, iterations, mismatch)
            changed = False
            for bus_index, role in enumerate(roles):
                if role != "PV":
                    continue
                connected_generators = [generator for generator in online if index[generator.bus_id] == bus_index]
                q_generation = calculated_q[bus_index] * network.base_mva + buses[bus_index].load_mvar
                q_min = sum(generator.q_min_mvar for generator in connected_generators)
                q_max = sum(generator.q_max_mvar for generator in connected_generators)
                if q_generation < q_min - 1e-6 or q_generation > q_max + 1e-6:
                    bounded_q = min(q_max, max(q_min, q_generation))
                    q_spec[bus_index] = (bounded_q - buses[bus_index].load_mvar) / network.base_mva
                    roles[bus_index] = "PQ"
                    messages.append(
                        f"Bus {buses[bus_index].id} converted PV→PQ because reactive generation {q_generation:.3f} Mvar exceeded [{q_min:.3f}, {q_max:.3f}] Mvar"
                    )
                    changed = True
            if not changed:
                break
        else:
            raise AnalysisError("Reactive-limit switching did not stabilize")

        assert last_result is not None
        voltages, calculated_p, calculated_q, iterations, mismatch = last_result
        branch_results = self._branch_flows(active_branches, voltages, index, network.base_mva)
        bus_results: list[ACBusResult] = []
        for bus_index, bus in enumerate(buses):
            vm = abs(voltages[bus_index])
            violation = vm < bus.voltage_min_pu - 1e-9 or vm > bus.voltage_max_pu + 1e-9
            bus_results.append(ACBusResult(
                bus.id,
                roles[bus_index],
                round(vm, 6),
                round(math.degrees(cmath.phase(voltages[bus_index])), 6),
                round(calculated_p[bus_index] * network.base_mva, 6),
                round(calculated_q[bus_index] * network.base_mva, 6),
                violation,
            ))
        total_p_loss = sum(flow.p_from_mw + flow.p_to_mw for flow in branch_results)
        total_q_loss = sum(flow.q_from_mvar + flow.q_to_mvar for flow in branch_results)
        slack_p = calculated_p[slack] * network.base_mva + buses[slack].load_mw
        slack_q = calculated_q[slack] * network.base_mva + buses[slack].load_mvar
        if any(item.voltage_violation for item in bus_results):
            messages.append("One or more bus-voltage limits are violated")
        if any(item.loading_pct > 100.0 + 1e-9 for item in branch_results):
            messages.append("One or more branch thermal limits are violated")
        return ACPowerFlowResult(
            converged=True,
            iterations=iterations,
            max_mismatch_mva=round(mismatch, 9),
            buses=bus_results,
            branches=branch_results,
            total_losses_mw=round(total_p_loss, 6),
            total_losses_mvar=round(total_q_loss, 6),
            slack_p_mw=round(slack_p, 6),
            slack_q_mvar=round(slack_q, 6),
            messages=messages,
        )

    @staticmethod
    def _assert_connected(network: NetworkModel, branches: Iterable[object]) -> None:
        adjacency = {bus.id: set() for bus in network.buses}
        for branch in branches:
            adjacency[branch.from_bus].add(branch.to_bus)
            adjacency[branch.to_bus].add(branch.from_bus)
        seen: set[str] = set()
        stack = [network.slack_bus_id]
        while stack:
            bus = stack.pop()
            if bus in seen:
                continue
            seen.add(bus)
            stack.extend(adjacency[bus] - seen)
        if len(seen) != len(adjacency):
            raise AnalysisError("AC power flow cannot solve an islanded network")

    @staticmethod
    def _ybus(network: NetworkModel, branches: list[object], index: dict[str, int]) -> list[list[complex]]:
        size = len(network.buses)
        ybus = [[0j for _ in range(size)] for _ in range(size)]
        for branch in branches:
            first, second = index[branch.from_bus], index[branch.to_bus]
            impedance = complex(branch.resistance_pu, branch.reactance_pu)
            if abs(impedance) < 1e-12:
                raise ValidationError(f"branch {branch.id}: zero impedance is not supported by AC solver")
            series = 1 / impedance
            charging = complex(0.0, branch.line_charging_pu / 2.0)
            tap = branch.tap_ratio * cmath.exp(1j * math.radians(branch.phase_shift_deg))
            ybus[first][first] += (series + charging) / (tap * tap.conjugate())
            ybus[first][second] -= series / tap.conjugate()
            ybus[second][first] -= series / tap
            ybus[second][second] += series + charging
        for bus_index, bus in enumerate(network.buses):
            ybus[bus_index][bus_index] += complex(bus.shunt_g_pu, bus.shunt_b_pu)
        return ybus

    @staticmethod
    def _specified_injections(network: NetworkModel, online: list[Generator], index: dict[str, int]) -> tuple[list[float], list[float]]:
        p_spec = [-bus.load_mw / network.base_mva for bus in network.buses]
        q_spec = [-bus.load_mvar / network.base_mva for bus in network.buses]
        for generator in online:
            bus_index = index[generator.bus_id]
            p_spec[bus_index] += generator.p_mw / network.base_mva
            q_spec[bus_index] += generator.q_mvar / network.base_mva
        return p_spec, q_spec

    @staticmethod
    def _bus_roles(network: NetworkModel, online: list[Generator], index: dict[str, int], slack: int) -> list[str]:
        generators_by_bus = {bus.id: [] for bus in network.buses}
        for generator in online:
            generators_by_bus[generator.bus_id].append(generator)
        roles: list[str] = []
        for bus_index, bus in enumerate(network.buses):
            explicit = bus.bus_type.upper()
            if bus_index == slack or explicit == "SLACK":
                roles.append("SLACK")
            elif explicit == "PV" or (explicit == "AUTO" and generators_by_bus[bus.id]):
                roles.append("PV")
            else:
                roles.append("PQ")
        return roles

    def _newton_solve(
        self,
        ybus: list[list[complex]],
        p_spec: list[float],
        q_spec: list[float],
        roles: list[str],
        buses: list[object],
        slack: int,
        base_mva: float,
        max_iterations: int,
        tolerance_mva: float,
    ) -> tuple[list[complex], list[float], list[float], int, float]:
        size = len(buses)
        vm = [bus.voltage_setpoint_pu for bus in buses]
        angles = [0.0 for _ in buses]
        non_slack = [index for index in range(size) if index != slack]
        pq = [index for index, role in enumerate(roles) if role == "PQ"]

        def residual(current_vm: list[float], current_angles: list[float]) -> tuple[list[float], list[float], list[float]]:
            voltages = [current_vm[index] * cmath.exp(1j * current_angles[index]) for index in range(size)]
            powers = [voltages[row] * (sum(ybus[row][column] * voltages[column] for column in range(size))).conjugate() for row in range(size)]
            calculated_p = [power.real for power in powers]
            calculated_q = [power.imag for power in powers]
            values = [p_spec[index] - calculated_p[index] for index in non_slack]
            values.extend(q_spec[index] - calculated_q[index] for index in pq)
            return values, calculated_p, calculated_q

        for iteration in range(1, max_iterations + 1):
            values, calculated_p, calculated_q = residual(vm, angles)
            mismatch = max((abs(value) for value in values), default=0.0) * base_mva
            if mismatch <= tolerance_mva:
                voltages = [vm[index] * cmath.exp(1j * angles[index]) for index in range(size)]
                return voltages, calculated_p, calculated_q, iteration - 1, mismatch
            variables: list[tuple[str, int]] = [("angle", index) for index in non_slack] + [("vm", index) for index in pq]
            jacobian = [[0.0 for _ in variables] for _ in values]
            for column, (kind, bus_index) in enumerate(variables):
                step = 1e-6
                plus_vm, minus_vm = vm[:], vm[:]
                plus_angles, minus_angles = angles[:], angles[:]
                if kind == "angle":
                    plus_angles[bus_index] += step
                    minus_angles[bus_index] -= step
                else:
                    plus_vm[bus_index] += step
                    minus_vm[bus_index] -= step
                plus, _, _ = residual(plus_vm, plus_angles)
                minus, _, _ = residual(minus_vm, minus_angles)
                for row in range(len(values)):
                    jacobian[row][column] = (plus[row] - minus[row]) / (2.0 * step)
            # residual is specified minus calculated power; Newton requires J·Δx = -residual.
            correction = _solve_linear(jacobian, [-value for value in values])
            for delta, (kind, bus_index) in zip(correction, variables):
                if kind == "angle":
                    angles[bus_index] += delta
                else:
                    vm[bus_index] += delta
                    if vm[bus_index] <= 0.05:
                        raise AnalysisError("AC Newton iteration produced a non-positive voltage")
        final_values, calculated_p, calculated_q = residual(vm, angles)
        mismatch = max((abs(value) for value in final_values), default=0.0) * base_mva
        raise AnalysisError(f"AC power flow did not converge in {max_iterations} iterations; final mismatch {mismatch:.6g} MVA")

    @staticmethod
    def _branch_flows(branches: list[object], voltages: list[complex], index: dict[str, int], base_mva: float) -> list[ACBranchFlow]:
        result: list[ACBranchFlow] = []
        for branch in branches:
            from_index, to_index = index[branch.from_bus], index[branch.to_bus]
            impedance = complex(branch.resistance_pu, branch.reactance_pu)
            series = 1 / impedance
            charging = complex(0.0, branch.line_charging_pu / 2.0)
            tap = branch.tap_ratio * cmath.exp(1j * math.radians(branch.phase_shift_deg))
            current_from = (series + charging) / (tap * tap.conjugate()) * voltages[from_index] - series / tap.conjugate() * voltages[to_index]
            current_to = -series / tap * voltages[from_index] + (series + charging) * voltages[to_index]
            power_from = voltages[from_index] * current_from.conjugate() * base_mva
            power_to = voltages[to_index] * current_to.conjugate() * base_mva
            mva_from, mva_to = abs(power_from), abs(power_to)
            loading = max(mva_from, mva_to) / branch.thermal_limit_mva * 100.0
            result.append(ACBranchFlow(
                branch.id, branch.from_bus, branch.to_bus,
                round(power_from.real, 6), round(power_from.imag, 6),
                round(power_to.real, 6), round(power_to.imag, 6),
                round(mva_from, 6), round(mva_to, 6), branch.thermal_limit_mva, round(loading, 6),
            ))
        return result


class EconomicDispatchEngine:
    """Quadratic-cost economic dispatch plus explicit AC feasibility validation."""

    def dispatch(self, network: NetworkModel, requested_mw: float | None = None) -> EconomicDispatchResult:
        network.require_valid()
        online = [generator for generator in network.generators if generator.in_service]
        flexible = [generator for generator in online if generator.dispatchable]
        fixed = [generator for generator in online if not generator.dispatchable]
        if not flexible:
            raise AnalysisError("Economic dispatch requires at least one online dispatchable generator")
        demand = sum(bus.load_mw for bus in network.buses) if requested_mw is None else requested_mw
        target = demand - sum(generator.p_mw for generator in fixed)
        total_min = sum(generator.p_min_mw for generator in flexible)
        total_max = sum(generator.p_max_mw for generator in flexible)
        messages: list[str] = []
        feasible = total_min - 1e-9 <= target <= total_max + 1e-9
        clipped_target = min(total_max, max(total_min, target))
        if not feasible:
            messages.append(f"Requested dispatch {target:.3f} MW is outside flexible range [{total_min:.3f}, {total_max:.3f}] MW")

        def output_for_lambda(generator: Generator, marginal: float) -> float:
            quadratic = max(generator.cost_quadratic, 1e-9)
            raw = (marginal - generator.cost_linear) / (2.0 * quadratic)
            return min(generator.p_max_mw, max(generator.p_min_mw, raw))

        low = min(2.0 * max(generator.cost_quadratic, 1e-9) * generator.p_min_mw + generator.cost_linear for generator in flexible) - 1.0
        high = max(2.0 * max(generator.cost_quadratic, 1e-9) * generator.p_max_mw + generator.cost_linear for generator in flexible) + 1.0
        for _ in range(100):
            midpoint = (low + high) / 2.0
            produced = sum(output_for_lambda(generator, midpoint) for generator in flexible)
            if produced < clipped_target:
                low = midpoint
            else:
                high = midpoint
        marginal = (low + high) / 2.0
        outputs = {generator.id: output_for_lambda(generator, marginal) for generator in flexible}
        for generator in fixed:
            outputs[generator.id] = generator.p_mw
        objective = sum(
            generator.cost_quadratic * outputs[generator.id] ** 2 + generator.cost_linear * outputs[generator.id] + generator.cost_constant
            for generator in online
        )
        records = [GeneratorDispatch(
            generator.id,
            round(outputs[generator.id], 6),
            generator.p_min_mw,
            generator.p_max_mw,
            round(2.0 * generator.cost_quadratic * outputs[generator.id] + generator.cost_linear, 6),
        ) for generator in online]
        return EconomicDispatchResult(
            feasible=feasible,
            requested_mw=round(demand, 6),
            dispatched_mw=round(sum(outputs.values()), 6),
            objective_cost_per_hour=round(objective, 6),
            marginal_cost=round(marginal, 6),
            generators=records,
            messages=messages,
        )

    def optimize_and_validate(self, network: NetworkModel, ac_engine: ACPowerFlowEngine | None = None) -> OperationalOptimizationResult:
        dispatch = self.dispatch(network)
        replacements = {record.generator_id: record.p_mw for record in dispatch.generators}
        dispatched_network = replace(network, generators=[replace(generator, p_mw=replacements[generator.id]) for generator in network.generators])
        try:
            ac_result = (ac_engine or ACPowerFlowEngine()).solve(dispatched_network)
        except (AnalysisError, ValidationError) as exc:
            return OperationalOptimizationResult(dispatch, None, False, [f"AC feasibility check failed: {exc}"])
        violations: list[str] = []
        if not dispatch.feasible:
            violations.extend(dispatch.messages)
        if any(item.voltage_violation for item in ac_result.buses):
            violations.append("AC voltage limits are violated")
        if any(item.loading_pct > 100.0 + 1e-9 for item in ac_result.branches):
            violations.append("AC thermal limits are violated")
        slack_generators = [generator for generator in dispatched_network.generators if generator.in_service and generator.bus_id == dispatched_network.slack_bus_id]
        slack_min, slack_max = sum(generator.p_min_mw for generator in slack_generators), sum(generator.p_max_mw for generator in slack_generators)
        if ac_result.slack_p_mw < slack_min - 1e-6 or ac_result.slack_p_mw > slack_max + 1e-6:
            violations.append(f"AC balancing slack dispatch {ac_result.slack_p_mw:.3f} MW is outside [{slack_min:.3f}, {slack_max:.3f}] MW")
        return OperationalOptimizationResult(dispatch, ac_result, not violations, violations)
