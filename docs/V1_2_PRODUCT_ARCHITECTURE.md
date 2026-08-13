# Grid Resilience Control Center v1.2.0 — Product Architecture

## Product scope

Grid Resilience Control Center is an engineering decision-support platform, not a supervisory-control system. The Windows application performs local model editing and screening studies, while the authenticated web control center governs scenarios, authorised telemetry snapshots, alarm review, data quality, and audit evidence. No SCADA/EMS write command, protection-setting change, or automatic field action is included in this release.

> **Stability-screening disclaimer.** The v1.2.0 transient module is a reduced-order, balanced positive-sequence simulation intended for engineering screening, education, and scenario comparison. It is not a validated RMS/EMT study engine and must not be used as the sole basis for protection coordination or real-time operational decisions.

## Engineering modules

| Module | v1.2.0 implementation boundary | Enterprise next step |
|---|---|---|
| Transient stability | Multi-machine classical swing-equation simulation, discrete fault/clearing events, rotor-angle and speed traces, CCT search | Validated machine, exciter, governor, relay and inverter model library |
| Contingency resilience | N-2 enumeration, overload cascade screening, severity score and non-binding remedial suggestions | AC security-constrained OPF and corrective-action optimisation |
| Network telemetry | Authorised upload or explicitly labelled simulated snapshot ingestion, quality flags, topology rendering | Read-only protocol gateway with OT segmentation and customer-approved connector |
| Scenario governance | Draft, reviewed and archived scenario records with immutable audit evidence | Four-eyes approval workflows, electronic signatures and retention policies |
| Reporting | HTML/PDF reports with provenance, analyst, timestamp and limitations | Approved templates, controlled branding and regulatory data-retention packs |

## Web control-center architecture

The web application applies server-side role enforcement before scenario, telemetry, alarm, report, and audit procedures. All business timestamps are stored in UTC and formatted at the browser boundary with the selected locale and time zone. Audit records are append-only, and each entry contains the prior digest and a digest over canonical event content. The UI never offers an edit or delete route for audit events.

| Role | Permitted work | Explicitly restricted |
|---|---|---|
| Viewer | Review dashboards, alarms and published reports | Imports, scenario changes and approvals |
| Analyst | Create scenarios, upload snapshots and run screening requests | Role changes and configuration of security controls |
| Operator | Review and acknowledge alarms, create operational notes | Model deletion, audit mutation and administrator functions |
| Administrator | Manage access roles, governance and retention settings | Audit-event mutation and field-device commands |

## International product readiness

The user experience supports English, Persian and Arabic. Persian and Arabic use an RTL document direction, while numerical values, UTC storage, user-selected time zone rendering, and unit labels remain unambiguous. The application must preserve keyboard navigation, visible focus states, contrast, reduced-motion support, and semantic labels across all language variants.

## Advanced commercial capabilities proposed beyond v1.2.0

| Capability | Commercial value | Implementation prerequisite |
|---|---|---|
| Read-only OT gateway | Allows governed integration with customer-approved telemetry sources | Network segmentation, vendor protocol support and threat model |
| Scenario approval workflow | Establishes four-eyes governance for regulated studies | Identity federation and organisation policy definition |
| Model provenance ledger | Makes model revisions and input data traceable across teams | Canonical model-hash scheme and object storage |
| Alarm correlation and suppression | Reduces duplicate alerts and operator noise | Defined alarm taxonomy and customer thresholds |
| Unit-system management | Supports per-unit, SI and regional reporting practices | Shared unit catalogue and conversion validation |
| Portfolio resilience scorecards | Gives executives comparable risk, readiness and trend views | Historical governed study and event data |
| Inverter-dominated-grid screening | Extends coverage to modern generation fleets | Validated control-model scope and benchmark cases |
| SSO and lifecycle provisioning | Fits enterprise identity governance | Customer IdP configuration and security review |

## References

[1] [PowerWorld, *Transient Stability Basics*](https://www.powerworld.com/files/T03StabilitySimulation_2019.pdf).

[2] [Microsoft Learn, *Set up signing integrations to use Artifact Signing*](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations).

[3] [ENTSO-E, *CIM for Grid Model Exchange*](https://www.entsoe.eu/digital/common-information-model/cim-for-grid-models-exchange/).
