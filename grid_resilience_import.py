"""Industrial exchange import adapters for Grid Resilience Studio.

The CDF parser implements the fixed-column IEEE Common Data Format bus/branch
subset.  The CIM/CGMES adapter is intentionally a transparent subset importer: it
reads RDF/XML profiles and produces an import report rather than claiming complete
CGMES conformity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re
from typing import Iterable
import xml.etree.ElementTree as ET
import zipfile

from grid_resilience import Branch, Bus, Generator, NetworkModel, ValidationError


@dataclass(frozen=True)
class ImportIssue:
    severity: str  # INFO, WARNING, ERROR
    code: str
    message: str
    source: str = ""


@dataclass
class ImportReport:
    source_format: str
    source_name: str
    issues: list[ImportIssue] = field(default_factory=list)
    profiles: list[str] = field(default_factory=list)
    model: NetworkModel | None = None

    @property
    def errors(self) -> list[ImportIssue]:
        return [issue for issue in self.issues if issue.severity == "ERROR"]

    @property
    def warnings(self) -> list[ImportIssue]:
        return [issue for issue in self.issues if issue.severity == "WARNING"]

    @property
    def ready_for_analysis(self) -> bool:
        return self.model is not None and not self.errors

    def add(self, severity: str, code: str, message: str, source: str = "") -> None:
        self.issues.append(ImportIssue(severity, code, message, source))


class IEECDFImporter:
    """Fixed-column IEEE CDF import with explicit OPF-data provenance warnings."""

    def load(self, path: str | Path) -> ImportReport:
        source = Path(path)
        return self.parse(source.read_text(encoding="utf-8", errors="replace"), source.name)

    def parse(self, text: str, source_name: str = "IEEE CDF") -> ImportReport:
        report = ImportReport("IEEE CDF", source_name)
        lines = text.splitlines()
        if not lines:
            report.add("ERROR", "CDF_EMPTY", "The CDF input is empty")
            return report
        base_mva = self._number(lines[0], 31, 37, 100.0)
        if base_mva <= 0:
            report.add("ERROR", "CDF_BASE_MVA", "The CDF MVA base must be positive", "title")
            return report
        bus_lines = self._section(lines, "BUS DATA FOLLOWS")
        branch_lines = self._section(lines, "BRANCH DATA FOLLOWS")
        if not bus_lines:
            report.add("ERROR", "CDF_BUS_SECTION", "BUS DATA FOLLOWS section was not found")
            return report
        if not branch_lines:
            report.add("ERROR", "CDF_BRANCH_SECTION", "BRANCH DATA FOLLOWS section was not found")
            return report

        buses: list[Bus] = []
        generators: list[Generator] = []
        for row, line in enumerate(bus_lines, start=1):
            bus_number = self._integer(line, 0, 4, None)
            if bus_number is None:
                report.add("ERROR", "CDF_BUS_NUMBER", "Bus number is missing or invalid", f"bus row {row}")
                continue
            bus_type_code = self._integer(line, 24, 26, 0) or 0
            role = {0: "PQ", 1: "PQ", 2: "PV", 3: "SLACK"}.get(bus_type_code)
            if role is None:
                report.add("ERROR", "CDF_BUS_TYPE", f"Unsupported bus type {bus_type_code}", f"bus {bus_number}")
                continue
            name = line[6:17].strip() or f"Bus {bus_number}"
            vm = self._number(line, 27, 33, 1.0)
            vset = self._number(line, 84, 90, vm if vm > 0 else 1.0)
            bus = Bus(
                id=str(bus_number), name=name, voltage_kv=self._number(line, 76, 83, 1.0),
                load_mw=max(0.0, self._number(line, 40, 49, 0.0)),
                load_mvar=max(0.0, self._number(line, 49, 59, 0.0)),
                is_slack=role == "SLACK", bus_type=role, voltage_setpoint_pu=vset if vset > 0 else 1.0,
                shunt_g_pu=self._number(line, 106, 114, 0.0), shunt_b_pu=self._number(line, 114, 122, 0.0),
                zone=str(self._integer(line, 20, 23, 0) or "Default"),
            )
            buses.append(bus)
            pg = self._number(line, 59, 67, 0.0)
            qg = self._number(line, 67, 75, 0.0)
            qmax = self._number(line, 90, 98, 100.0)
            qmin = self._number(line, 98, 106, -100.0)
            if role in {"PV", "SLACK"}:
                pmax = max(pg + base_mva, 0.0)
                generators.append(Generator(
                    id=f"GEN-{bus_number}", name=f"CDF generator at {name}", bus_id=str(bus_number),
                    p_mw=max(0.0, pg), p_max_mw=pmax, q_mvar=qg, q_min_mvar=qmin, q_max_mvar=max(qmax, qmin + 0.001),
                    voltage_setpoint_pu=bus.voltage_setpoint_pu,
                ))
                report.add("WARNING", "CDF_OPF_DEFAULTS", f"Generator GEN-{bus_number} has inferred Pmin/Pmax and cost coefficients; review before OPF", f"bus {bus_number}")

        branches: list[Branch] = []
        known_buses = {bus.id for bus in buses}
        for row, line in enumerate(branch_lines, start=1):
            from_bus = self._integer(line, 0, 4, None)
            to_bus = self._integer(line, 5, 9, None)
            if from_bus is None or to_bus is None:
                report.add("ERROR", "CDF_BRANCH_ENDPOINT", "Branch endpoint is missing or invalid", f"branch row {row}")
                continue
            if str(from_bus) not in known_buses or str(to_bus) not in known_buses:
                report.add("ERROR", "CDF_UNKNOWN_BUS", f"Branch references an unknown bus ({from_bus}, {to_bus})", f"branch row {row}")
                continue
            resistance = self._number(line, 19, 29, 0.0)
            reactance = self._number(line, 29, 40, 0.0)
            if abs(reactance) < 1e-12:
                report.add("ERROR", "CDF_ZERO_REACTANCE", "Zero-reactance branches are not supported", f"branch {from_bus}-{to_bus}")
                continue
            rating = self._number(line, 50, 55, 0.0)
            if rating <= 0:
                rating = 99.0 * base_mva
                report.add("WARNING", "CDF_DEFAULT_RATING", f"Branch {from_bus}-{to_bus} has no Rate A; assigned {rating:.1f} MVA", f"branch row {row}")
            tap = self._number(line, 76, 82, 1.0)
            branches.append(Branch(
                id=f"BR-{row}", name=f"CDF {from_bus}–{to_bus}", from_bus=str(from_bus), to_bus=str(to_bus),
                reactance_pu=abs(reactance), thermal_limit_mva=rating, resistance_pu=max(0.0, resistance),
                line_charging_pu=self._number(line, 40, 50, 0.0), tap_ratio=tap if tap > 0 else 1.0,
                phase_shift_deg=self._number(line, 83, 90, 0.0),
            ))
        self._finish(report, source_name, base_mva, buses, branches, generators, "Imported from IEEE CDF; review inferred operational and economic data before optimization.")
        return report

    @staticmethod
    def _section(lines: list[str], heading: str) -> list[str]:
        start = next((index + 1 for index, line in enumerate(lines) if heading in line.upper()), None)
        if start is None:
            return []
        result: list[str] = []
        for line in lines[start:]:
            if line.lstrip().startswith("-999"):
                break
            if line.strip():
                result.append(line.rstrip("\n"))
        return result

    @staticmethod
    def _number(line: str, begin: int, end: int, default: float) -> float:
        value = line[begin:end].strip()
        try:
            return float(value) if value else default
        except ValueError:
            return default

    @staticmethod
    def _integer(line: str, begin: int, end: int, default: int | None) -> int | None:
        value = line[begin:end].strip()
        try:
            return int(value) if value else default
        except ValueError:
            return default

    @staticmethod
    def _finish(report: ImportReport, source_name: str, base_mva: float, buses: list[Bus], branches: list[Branch], generators: list[Generator], description: str) -> None:
        if report.errors:
            return
        if not buses or not branches:
            report.add("ERROR", "IMPORT_EMPTY_NETWORK", "Importer did not produce both buses and branches")
            return
        if sum(bus.is_slack for bus in buses) != 1:
            report.add("ERROR", "IMPORT_SLACK", "Exactly one slack bus is required for analysis")
            return
        if not any(generator.bus_id == next(bus.id for bus in buses if bus.is_slack) for generator in generators):
            report.add("ERROR", "IMPORT_SLACK_GENERATOR", "No generator is attached to the imported slack bus")
            return
        candidate = NetworkModel(name=Path(source_name).stem or "Imported network", base_mva=base_mva, buses=buses, branches=branches, generators=generators, description=description, tags=["imported"])
        try:
            candidate.require_valid()
        except ValidationError as exc:
            report.add("ERROR", "IMPORT_VALIDATION", str(exc))
            return
        report.model = candidate
        report.add("INFO", "IMPORT_READY", f"Imported {len(buses)} buses, {len(branches)} branches and {len(generators)} generators")


class CIMCGMESImporter:
    """Safe RDF/XML profile scanner and operational-network subset importer."""

    MAX_ARCHIVE_BYTES = 100 * 1024 * 1024

    def load(self, path: str | Path) -> ImportReport:
        source = Path(path)
        if source.suffix.lower() == ".zip":
            return self._from_zip(source)
        return self.parse_xml_documents([(source.name, source.read_bytes())], source.name)

    def _from_zip(self, source: Path) -> ImportReport:
        report = ImportReport("CIM/CGMES subset", source.name)
        try:
            with zipfile.ZipFile(source) as archive:
                members = [member for member in archive.infolist() if not member.is_dir() and member.filename.lower().endswith((".xml", ".rdf"))]
                total = sum(member.file_size for member in members)
                if total > self.MAX_ARCHIVE_BYTES:
                    report.add("ERROR", "CGMES_ARCHIVE_LIMIT", "CGMES archive exceeds the safe uncompressed size limit")
                    return report
                documents = [(member.filename, archive.read(member)) for member in members]
        except (OSError, zipfile.BadZipFile) as exc:
            report.add("ERROR", "CGMES_ARCHIVE", f"Could not read CGMES archive: {exc}")
            return report
        if not documents:
            report.add("ERROR", "CGMES_NO_XML", "Archive contains no XML/RDF documents")
            return report
        return self.parse_xml_documents(documents, source.name)

    def parse_xml_documents(self, documents: Iterable[tuple[str, bytes]], source_name: str = "CIM/CGMES") -> ImportReport:
        report = ImportReport("CIM/CGMES subset", source_name)
        elements: dict[str, tuple[str, ET.Element, str]] = {}
        for filename, raw in documents:
            try:
                root = ET.fromstring(raw)
            except ET.ParseError as exc:
                report.add("ERROR", "CGMES_XML", f"Invalid XML: {exc}", filename)
                continue
            report.profiles.append(filename)
            for child in root:
                identifier = self._identifier(child)
                if identifier:
                    elements[identifier] = (self._local(child.tag), child, filename)
        if report.errors:
            return report
        if not elements:
            report.add("ERROR", "CGMES_EMPTY", "No identifiable CIM resources were found")
            return report

        terminals: dict[str, list[str]] = {}
        for _, (kind, element, _) in elements.items():
            if kind != "Terminal":
                continue
            equipment = self._reference(element, "ConductingEquipment")
            bus = self._reference(element, "TopologicalNode") or self._reference(element, "ConnectivityNode")
            if equipment and bus:
                terminals.setdefault(equipment, []).append(bus)

        node_ids = {bus for connected in terminals.values() for bus in connected}
        if not node_ids:
            node_ids = {identifier for identifier, (kind, _, _) in elements.items() if kind in {"TopologicalNode", "ConnectivityNode"}}
        buses: list[Bus] = []
        base_voltage = self._base_voltages(elements)
        external_nodes = {bus for identifier, (kind, _, _) in elements.items() if kind in {"ExternalNetworkInjection", "EnergySource"} for bus in terminals.get(identifier, [])}
        for identifier in sorted(node_ids):
            record = elements.get(identifier)
            if record is None:
                report.add("WARNING", "CGMES_UNKNOWN_NODE", f"Terminal references node {identifier} that is absent from profiles")
                continue
            kind, element, _ = record
            nominal = self._find_nominal_voltage(element, base_voltage) or 110.0
            buses.append(Bus(identifier, self._child_text(element, "name") or identifier, nominal, is_slack=identifier in external_nodes, bus_type="SLACK" if identifier in external_nodes else "AUTO"))
        if not buses:
            report.add("ERROR", "CGMES_NO_BUSES", "No terminal-connected topology nodes were found")
            return report
        if not any(bus.is_slack for bus in buses):
            buses[0] = Bus(**{**buses[0].__dict__, "is_slack": True, "bus_type": "SLACK"})
            report.add("WARNING", "CGMES_INFERRED_SLACK", f"No ExternalNetworkInjection was found; {buses[0].id} was selected as screening slack")
        if sum(bus.is_slack for bus in buses) > 1:
            chosen = next(bus.id for bus in buses if bus.is_slack)
            buses = [Bus(**{**bus.__dict__, "is_slack": bus.id == chosen, "bus_type": "SLACK" if bus.id == chosen else "AUTO"}) for bus in buses]
            report.add("WARNING", "CGMES_MULTI_SLACK", f"Multiple external injections found; {chosen} was retained as screening slack")

        bus_ids = {bus.id for bus in buses}
        generators: list[Generator] = []
        branches: list[Branch] = []
        for identifier, (kind, element, filename) in elements.items():
            connected = [bus for bus in terminals.get(identifier, []) if bus in bus_ids]
            if kind == "EnergyConsumer" and connected:
                bus_id = connected[0]
                bus_index = next(index for index, bus in enumerate(buses) if bus.id == bus_id)
                buses[bus_index] = Bus(**{**buses[bus_index].__dict__, "load_mw": max(0.0, self._float(element, "p", 0.0)), "load_mvar": max(0.0, self._float(element, "q", 0.0))})
            elif kind in {"SynchronousMachine", "ExternalNetworkInjection", "EnergySource"} and connected:
                p = abs(self._float(element, "p", 0.0))
                q = self._float(element, "q", 0.0)
                generators.append(Generator(identifier, self._child_text(element, "name") or kind, connected[0], p, max(p + 100.0, 100.0), q_mvar=q))
                report.add("WARNING", "CGMES_OPF_DEFAULTS", f"Generator {identifier} uses screening P/Q limits and cost defaults; review before OPF", filename)
            elif kind == "ACLineSegment":
                if len(connected) != 2:
                    report.add("WARNING", "CGMES_LINE_TERMINALS", f"ACLineSegment {identifier} does not resolve to two internal terminal nodes", filename)
                    continue
                reactance = abs(self._float(element, "x", 0.0))
                if reactance <= 1e-12:
                    report.add("WARNING", "CGMES_LINE_X", f"ACLineSegment {identifier} has no usable reactance and was skipped", filename)
                    continue
                branches.append(Branch(identifier, self._child_text(element, "name") or identifier, connected[0], connected[1], reactance, 9900.0, resistance_pu=max(0.0, self._float(element, "r", 0.0)), line_charging_pu=self._float(element, "bch", 0.0)))
            elif kind in {"PowerTransformer", "TapChanger", "Switch", "Breaker"}:
                report.add("WARNING", "CGMES_UNSUPPORTED_EQUIPMENT", f"{kind} {identifier} is scanned but not converted by the v1.1 subset importer", filename)
        slack_id = next(bus.id for bus in buses if bus.is_slack)
        if not any(generator.bus_id == slack_id for generator in generators):
            generators.append(Generator("CGMES-SLACK", "Imported external grid", slack_id, 0.0, 1e6))
            report.add("WARNING", "CGMES_SLACK_GENERATOR", "Added an unconstrained screening slack generator; replace with verified source data before OPF")
        IEECDFImporter._finish(report, source_name, 100.0, buses, branches, generators, "Imported from CIM/CGMES subset; profile, topology and parameter coverage must be reviewed before operational use.")
        if report.model:
            report.add("INFO", "CGMES_SUBSET", "CIM/CGMES subset import completed. This is not a claim of CGMES conformance.")
        return report

    @staticmethod
    def _local(tag: str) -> str:
        return tag.split("}")[-1].split(".")[-1]

    def _identifier(self, element: ET.Element) -> str | None:
        for key, value in element.attrib.items():
            if key.endswith("}ID") or key.endswith("}about") or key in {"ID", "about"}:
                return value.lstrip("#")
        return self._child_text(element, "mRID")

    def _reference(self, element: ET.Element, property_name: str) -> str | None:
        for child in element:
            if self._local(child.tag) == property_name:
                for key, value in child.attrib.items():
                    if key.endswith("}resource") or key == "resource":
                        return value.lstrip("#")
        return None

    def _child_text(self, element: ET.Element, property_name: str) -> str | None:
        for child in element:
            if self._local(child.tag) == property_name and child.text and child.text.strip():
                return child.text.strip()
        return None

    def _float(self, element: ET.Element, property_name: str, default: float) -> float:
        raw = self._child_text(element, property_name)
        try:
            return float(raw) if raw is not None else default
        except ValueError:
            return default

    def _base_voltages(self, elements: dict[str, tuple[str, ET.Element, str]]) -> dict[str, float]:
        result: dict[str, float] = {}
        for identifier, (kind, element, _) in elements.items():
            if kind == "BaseVoltage":
                result[identifier] = self._float(element, "nominalVoltage", 0.0)
        return result

    def _find_nominal_voltage(self, element: ET.Element, base_voltages: dict[str, float]) -> float | None:
        direct = self._float(element, "nominalVoltage", 0.0)
        if direct > 0:
            return direct
        referenced = self._reference(element, "BaseVoltage")
        return base_voltages.get(referenced or "")
