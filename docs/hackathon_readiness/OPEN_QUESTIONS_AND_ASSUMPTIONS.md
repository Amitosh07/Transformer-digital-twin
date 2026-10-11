# Open questions and assumptions

Current definitive scope: Modbus transmission, IoT, mandatory RUL and energy priorities come from the user's confirmed context. Live college telemetry is unconfirmed. Earlier “organizer requirement unresolved” RUL status is stale. There is no need to reopen whether RUL is required; clarification concerns the accepted evidence/method.

| ID / unresolved evidence | Who can answer | Impact / safe interim decision |
|---|---|---|
| Q01 existing raw data, fitted parameters, evaluation report and release manifest | ML lead | Retrieve original versioned bundle and verify hashes; do not rebuild all phases or quote unverified historical metrics. Coded defaults allowed only as labelled unverified/demo config. |
| Q02 exact `(2)` workbook version and finale dataset delivery | Team lead / organizers | Only supplied unnumbered workbook inspected. Build adapter-friendly replay/simulator now; do not promise an unseen dataset/date/fields. |
| Q03 actual transformer id/nameplate and sensor location/side | Operator / organizers | Record kVA, HV/LV volts, current/side, phase count, Hz, vector group, impedance %, cooling, liquid/insulation, applicable rise limits and provenance. Fictional demo assets stay fictional. |
| Q04 source oil/ambient/WTI/oil-level units and alarm/contact meaning | Dataset provider / meter manual / operator | Source-unit analytics only; WTI status not continuous °C, unknown contact not clear, unknown level not percent. |
| Q05 public data timezone and meter interval/counter meaning | Dataset provider | Preserve unknown historic source time until explicit staging/replay policy; simulator uses declared UTC; backend requires aware timestamps. |
| Q06 stable register map/device protocol | Simulator owner for demo; operator/OEM for live | Define one versioned demo input-register map; do not infer OEM addresses/types/scales or write control registers. |
| Q07 permitted college telemetry and network access | College substation operator / institutional authority | Assume unavailable; use laptop TCP simulation. No panel wiring or production control access. |
| Q08 RUL demonstration evidence expected and endpoint | Organizers / team lead | Build labelled simulated degradation first-passage RUL plus insufficient-data real-asset contract. No trained accuracy or real-life countdown. Ask whether conditional insulation-life budget presentation meets expectations. |
| Q09 baseline service age/degradation/life budget | Asset operator / maintenance records | Without consumed exposure and justified budget, thermal-ageing RUL stays null. Recent stress is not absolute residual life. |
| Q10 thermal/loss/hot-spot and insulation parameters | OEM test report / selected standard / operator | Enable only eligible physical model; no universal guessed constants or rise limits. Catalogue access does not establish full clause compliance. |
| Q11 active/energy meter units, sign, resets/rollover, input/output boundary | Meter/OEM/data provider | Label simulated energy or qualified source units; no measured efficiency/loss/savings from one unknown meter. |
| Q12 ML history/state/worker/deployment ownership | Backend + ML owners | One demo ML owner, explicit warm-up/checkpoint policy; no unsupported horizontal worker promise. Resolve SQL rollback and conflict policy before integrated demo. |
| Q13 actual runtime dependencies, PostgreSQL/migrations, broker/frontend URLs | DevOps + backend/frontend | Prepare `.env`, actual ML packaging, CORS for chosen React origin, and run existing DB checks on team machine. Audit used no live DB/Docker. |
| Q14 25-assets scope and target rate | Team lead / organizers if official scale required | Demonstrate 25 simulated ids at proposed 5s cadence; no 25 live-device claim. Performance targets are team proposals. |
| Q15 protection settings and trip-latch clearing authority | Operator for live, simulator contract for demo | Advisory outputs only; demo contacts labelled synthetic. Maintenance completion does not implicitly clear physical trip state. |
| Q16 reporting/download format | Team lead / frontend | PDF typical architecture suggests summaries. Prioritize complete monitoring/RUL/energy flow; add source-labelled CSV/report export as P2 if required. |

## Explicit interim assumptions

- The pinned commit represents committed current work; teammates' uncommitted files and deployments were not accessible. Audit findings apply to that snapshot.
- The chosen frontend remains React/Vite; no unnecessary Streamlit rewrite. Existing visual elements are reusable but need API-driven data.
- Local simulation does not require real sensors, RS-485 hardware or college access. Pymodbus stable API/version must be pinned/tested.
- Thermal/anomaly/HI/maintenance code and tests are preserved. Repairs target demonstrated integration/state/artifact defects, not methodology replacement.
- Operational fault_risk remains null until appropriate temporal validation supports release. Simulated RUL does not unlock forecast probability.
- Proposed 2–5s UI polling, 5s stream, 10s demo staleness/latency and 30min 25-asset test are engineering acceptance choices, not CPRI judging requirements. Real-source freshness follows actual cadence.
- Simulation and replay retain event time; wall acceleration is explicit. Unknown historical timezones/units are not transformed by guesswork.
- All live acquisition remains read-only under explicit operator authorization. No control writes or simulated protection settings become real operating limits.

## Sources and limits

Reviewed 9 October 2026: official PowerNext abstract https://www.powernext-ai.in/problem-statements; Modbus https://modbus.org/modbus-specifications and TCP implementation guide https://modbus.org/file/secure/messagingimplementationguide.pdf; OASIS MQTT 3.1.1 https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html and 5.0 https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html; pymodbus stable https://pymodbus.readthedocs.io/en/stable/source/server.html; IEC catalogue entries https://webstore.iec.ch/en/publication/34351 and https://webstore.iec.ch/en/publication/599. IEEE and DOE targeted sources and their access limits are recorded in [RUL_AND_ENERGY_STRATEGY.md](RUL_AND_ENERGY_STRATEGY.md).

Full paid standards and research papers were not acquired; no standards certification claimed. Provided email screenshots were visually read, not authenticated against an inbox. Two dashboard references are blurry and support layout only. Historical public CSVs, fitted artifact hashes, empirical metrics, real-device protocol/readability, live DB/containers/browser demo and achieved portfolio capacity remain unverified. No current or future dataset availability or judging weights are invented.

Stop after Part 1. Team decisions from this bundle can inform separately requested Part 2 implementation prompts; none are created here.
