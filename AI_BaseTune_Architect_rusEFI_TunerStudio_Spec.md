
# AI BaseTune Architect — rusEFI + TunerStudio
**Master specification, design, and implementation guide**  
Status: Draft — production-grade specification suitable to hand to a coding agent / small engineering team.

---

> NOTE: This document describes a safety-first, production-oriented system for AI-assisted base-tune generation and controlled live tuning using a rusEFI ECU and TunerStudio as the front-end. It assumes the builder will follow all local laws and safety best practices and that the operator has access to dyno testing or a safe environment for verification.

---

## Table of Contents
1. Executive summary
2. Goals & constraints
3. End‑to‑end architecture
4. Component specifications
   - Companion Service
   - TunerStudio Integration / UI
   - rusEFI firmware interactions
   - Local LLM runtime & model choices
5. Data models & JSON schemas
6. Deterministic engine model
   - Injector scaling
   - Airflow / VE estimation
   - Ignition baseline generator
   - Boost & torque mapping
7. Guardrail engine: rules & safety
8. Prompt templates & RAG knowledge base
9. Full plugin/service API design
10. UI / UX design (non-tuner flows)
11. Live one‑session power ramp algorithm
12. Logging, audit, rollback, and forensics
13. Security & signing
14. Testing plan & acceptance criteria
15. Deployment & ops (Windows-focused)
16. Developer handoff checklist & milestones
17. Appendix: formulas, example configs, test datalogs

---

# 1. Executive summary
Build **AI BaseTune Architect**, a local-first system that:
- Accepts a detailed Build Profile for a vehicle (engine, induction, fuel, ignition, sensors).
- Deterministically computes a conservative, runnable base calibration (fuel, ignition, boost maps) for rusEFI.
- Uses a local LLM to augment reasoning (strategy selection, explanations, troubleshooting).
- Enforces hard safety guardrails and requires explicit approvals for higher‑risk actions (ignition, boost).
- Optionally performs controlled live fuel auto-corrections and a staged power ramp toward a target horsepower in a monitored environment (dyno or closed track).

Primary design constraints:
- Offline-first / localhost-only by default
- Deterministic physics engine as the basis for all table generation
- LLM as advisor / strategist, not as the final authority
- Firmware-level safety (rusEFI) always active

---

# 2. Goals & constraints
**Primary goals**
- Produce a safe base tune that will start, idle, and be drivable for initial testing.
- Provide non-tuner friendly UX to explain and apply changes.
- Allow controlled live fuel-only auto-corrections.
- Provide an optional supervised power-ramp procedure to approach a horsepower target.

**Hard constraints**
- Never allow automatic ignition increases beyond conservative thresholds without explicit multi-step approvals.
- Injector duty must remain under safe duty limits.
- Knock detection must trigger immediate rollback or ignition retard actions implemented in firmware.
- All network endpoints are localhost by default.

---

# 3. End‑to‑end architecture (text diagram)

```
TunerStudio UI (Webview Panel or External React App)
  ↕ (local HTTP / WebSocket)
Companion Service (FastAPI)  <-->  Local LLM runtime (llama.cpp / Ollama / vLLM)
  ↕
rusEFI ECU (serial/USB CAN) <-> TunerStudio <-> Companion (streams telemetry, writes tables)
Audit Store (snapshots + signed logs)
```

**Notes**
- TunerStudio is the user-facing host for dashboards and live connect.
- Companion Service performs pre-processing, deterministic calculations, model-adapter calls, guardrail validation, signing, logging, and acts as the sole authority to produce structured recommendations to the plugin/UI.
- The LLM only receives compact, preprocessed summaries and the vehicle profile + relevant references from the knowledge base (RAG).

---

# 4. Component specifications

## 4.1 Companion Service (recommended: Python 3.10+, FastAPI)
Responsibilities:
- HTTP & WebSocket API for TunerStudio plugin / UI
- Preprocessing telemetry & datalogs
- Deterministic baseline map generator (core math)
- Model adapter (local LLM or optional cloud)
- Guardrail engine (validation & clamping)
- Applier orchestration (snapshots, writetables via TunerStudio command)
- Audit & rollback store
- HMAC signing of responses

Key modules:
- `api` (FastAPI endpoints)
- `preprocessor` (datalog → cell summary)
- `engine_model` (deterministic math unit)
- `model_adapter` (LLM call wrapper)
- `guardrails` (validated constraints)
- `applier` (orchestration & snapshots)
- `storage` (sqlite for metadata + file store for snapshots)
- `auth` (HMAC key manager)

## 4.2 TunerStudio Integration
Options:
- Build a TunerStudio plugin if supported (native plugin SDK) OR
- Use an embedded WebView that the plugin launches and which communicates with the Companion over `http://localhost:PORT`.
- Provide a small Lua/script snippet (if TunerStudio scripting supports it) or use TunerStudio’s Autoserver API to fetch/writetables.

UI elements:
- Build Profile wizard
- Chat + Assistant pane
- Datalog upload drag/drop
- Heatmap tables overlay
- Live monitor & safety bar
- Apply controls (Per-cell approve, Apply All clamped, Auto-apply toggle)
- One‑Shot Mode: Power Ramp controller with progress UI and emergency stop

## 4.3 rusEFI considerations
- rusEFI firmware must have the required channels exposed: VE tables, fuel tables, ignition tables, boost tables, wideband feedback, knock counters, IAT/ECT, MAP, RPM, TPS.
- ruSEFI supports live streaming via its protocol; Companion should read via TunerStudio or direct serial if privileged.
- Firmware-level limits should be set (max advance, max requested boost) as a final hardware guard.

## 4.4 Local LLM runtime
- Allowed models: quantized 7B (minimum), 13B preferred for better reasoning.
- Runtimes: Ollama, llama.cpp (ggml), vLLM. Choose based on hardware.
- Model settings: temperature 0.0–0.2, deterministic decoding (top_p low), max tokens bounded.
- Model adapter must enforce JSON-only output and validate.

---

# 5. Data models & JSON schemas

All API calls and model exchanges MUST follow these JSON schemas. Validation MUST be performed server-side.

## 5.1 Vehicle profile (`VehicleProfile`)
```json
{
  "vehicle_id": "uuid",
  "make": "string",
  "model": "string",
  "engine_family": "string",
  "displacement_l": "number",
  "cylinders": "integer",
  "aspiration": "turbo|na|supercharged",
  "compression_ratio": "number",
  "fuel_type": "gas93|gas98|e85|custom",
  "injector_cc_min": "number",
  "fuel_pressure_psi": "number",
  "max_safe_rpm": "integer",
  "turbo_model": "string|null",
  "wastegate_type": "internal|external|null",
  "target_hp": "number|null",
  "usage": "street|track|dyno",
  "notes": "string|null"
}
```

## 5.2 Calibration snapshot (`CalibrationSnapshot`)
Contains table axes and raw tables in normalized units.

```json
{
 "axes": {
   "rpm": [ "number", ... ],
   "map_kpa": [ "number", ... ]
 },
 "fuel_table": [[ "number" ]],
 "ignition_table": [[ "number" ]],
 "boost_table": [[ "number" ]],
 "metadata": { "timestamp": "ISO8601", "source": "tunerstudio" }
}
```

## 5.3 Datalog cell summary (`DatalogSummary`)
```json
{
  "session_id": "uuid",
  "cells": [
    {
      "rpm_index": "integer",
      "map_index": "integer",
      "occupied_pct": "number",
      "target_afr": "number|null",
      "measured_afr": "number|null",
      "afr_error_pct": "number|null",
      "knock_count": "integer",
      "iat_c": "number",
      "ect_c": "number",
      "lambda_corrections": "number"
    }
  ],
  "global_stats": {
    "max_knock_cell": { "rpm_index": "int", "map_index": "int" },
    "avg_iat_c": "number",
    "max_injector_duty_pct": "number"
  }
}
```

## 5.4 Analysis request (`/analyze` payload)
```json
{
  "vehicle_profile": { ... },
  "calibration": { ... },
  "datalog_summary": { ... },
  "options": {
    "mode": "advisory|suggested_apply|limited_auto_apply",
    "aggressiveness": "conservative|balanced|aggressive",
    "max_fuel_delta_pct": 5.0,
    "max_ignition_delta_deg": 2.0
  }
}
```

## 5.5 Analysis response
```json
{
 "session_id": "uuid",
 "timestamp": "ISO8601",
 "recommendations": [
   {
     "rpm_index": 0,
     "map_index": 0,
     "delta_fuel_pct": 0.0,
     "delta_ign_deg": 0.0,
     "confidence": 0.0,
     "rationale": "string"
   }
 ],
 "summary_text": "string",
 "warnings": [ "string" ],
 "signature": "HMAC_SHA256"
}
```

---

# 6. Deterministic engine model (fully specified)

This is the foundation. The coding agent must implement these formulas exactly.

## 6.1 Units & conventions
- Displacement in liters (L)
- Injector flow in cc/min at reference pressure (commonly 3 bar/43.5psi)
- MAP in kPa absolute (sea level 101.325 kPa)
- AFR stoichiometric reference by fuel type (gasoline 14.7, E85 ~9.8)
- Air density corrections via IAT (Kelvin) and barometric pressure assumed standard unless sensor present.

## 6.2 Injector flow scaling & deadtime
1. Compute mass flow per injection event:
   - Convert cc/min to cc/sec: `flow_cc_s = injector_cc_min / 60`
   - Convert to mass: requires fuel density; use 0.75 kg/L for petrol approximations, but for base setup use volumetric logic: compute required injected volume per stroke from target AFR using air mass estimate (see below).
2. Deadtime lookup curve: installer can supply deadtime curve or use conservative fixed deadtime (e.g., 1.0 ms) and force mapping to actual injector type later.

Implement accurate injector model if deadtime curve available:
```
pulsewidth_ms = (fuel_mass_per_cycle / injector_mass_flow_rate) * 1000 + injector_deadtime_ms
```

For initial base tune, compute the Scaling Factor (Injector Constant) to set VE/fuel scalar.

## 6.3 Air mass & VE estimation
Use ideal gas relation approximations for initial estimates:

`air_mass_per_cycle_grams = (VE_cell * displacement_l * 1000) * (map_kpa / 101.325) * (288 / (273 + IAT_c)) * (1 / 2)`

Where VE_cell initial guess = 0.75 (75%) for most cells; tuned by the VE learning process.

Provide the coding agent with VE generator algorithm:
- Start VE baseline grid with monotonic smooth function across rpm and map axes
- VE increases with RPM and load; for turbo, make VE function that increases across MAP bands

Implement a smoothing filter on generated VE (e.g., 2D Gaussian smoothing via convolution kernel size 3x3).

## 6.4 Base AFR targets
Define profile by usage & fuel:
- Street / gas93:
  - Idle: 13.5–14.2
  - Cruise: 14.2–14.8
  - Mid load: 12.5–13.2
  - Boost: 11.5–12.0
- Track / gas98: slightly richer mid and boost targets
- E85: boost targets are richer (11.0–11.6)

Coding agent must implement mapping rules and axis interpolation.

## 6.5 Ignition baseline generation
Approach:
- Start with conservative ignition map:
  - Determine baseline MBT window for displacement & compression ratio from knowledge base (typical MBT ~ 26–34° for NA petrol depending on compression).
  - For turbo and boost cells, reduce timing with rule: `timing_base = mbt_estimate - timing_safety_margin`, where safety margin depends on boost & fuel (e.g., +1° margin per 10 kPa boost).
- Use lookup table to apply IAT & ECT retard on cells predicted to be hot.

Implement deterministic cap: do not exceed `max_total_ignition_increase` configured globally (default +6° over baseline).

## 6.6 Boost & torque mapping
- Use turbo database lookup to estimate approximate required boost for given airflow target at target HP.
- Conservative boost curve generator: linear ramp across RPM with soft saturation near redline.
- Torque estimation: rough approximation using `HP = torque * RPM / 5252` and air mass flow → torque estimate.

---

# 7. Guardrail engine: rules & safety (complete list)

All rules enforced server-side before any apply:

1. **Injector duty clamp**
   - Max injector duty default = 85%. Configurable, but require explicit confirmation for >85%.

2. **Per-cell max delta**
   - default fuel delta ≤ ±5% per apply operation (suggested), cumulative limit per session configurable.

3. **Ignition rules**
   - No ignition increase in any cell with `knock_count > 0`.
   - For ignition increases: require additional explicit user approval if any delta > 1.5°.
   - Cumulative ignition increase for entire table ≤ +6° unless user uses expert override with dyno mode.

4. **Occupancy**
   - Do not change cells where `occupied_pct < 3–5%` unless user explicitly overrides.

5. **IAT/ECT trending**
   - If IAT rising rapidly or exceeding threshold (user configurable), restrict ignition & boost changes.

6. **Auto-apply live safety**
   - Fuel-only changes allowed.
   - Rate-of-change: max 2% fuel per 30s, must hold AFR steadiness for 10s before next change.
   - Immediate rollback if knock_count spikes or AFR mirror deviates >5%.

7. **Emergency stop**
   - Kill auto-apply process and revert last safe snapshot if any safety condition triggers.

8. **Signature & audit**
   - All recommendations must be signed by Companion Service HMAC and accompanied by a snapshot id.

9. **Approval workflow**
   - Advisory mode: no writes.
   - Suggested_apply: show per-cell and global summary with approve buttons.
   - Limited_auto_apply: fuel-only; user must toggle and accept risks in a modal with explicit consent.

---

# 8. Prompt templates, RAG & Knowledge Base

## 8.1 RAG knowledge base
Content:
- Engine family pages (B-series, K-series, LS, etc.)
- Fuel behavior docs
- Turbo characteristic pages
- Injector deadtime curves
- rusEFI firmware docs (channels, limits)
- TunerStudio usage docs
- Sample dyno sessions with annotated recommended deltas

Store as vector embeddings (Milvus, Weaviate, or local FAISS) for retrieval.

## 8.2 System prompt template (strict)
```
SYSTEM:
You are an automotive ECU calibration assistant operating under strict safety constraints. 
Receive only structured JSON and output only JSON that conforms exactly to the schema provided. 
Never recommend actions that violate the Guardian rules provided. 
When in doubt, output advisory text and set "confidence" low.

USER:
VehicleProfile: { ... }
CalibrationSnapshot: { ... }
DatalogSummary: { ... }
Options: { ... }
RelevantKnowledgeDocs: [ <short retrieval snippets> ]
Task: Provide per-cell recommendations (delta_fuel_pct, delta_ign_deg), a human-readable summary, and warnings.
```

Enforce deterministic settings: temperature=0.1, max_tokens limited (e.g., 1024), stop on JSON block close.

---

# 9. Full plugin/service API design (endpoints)

Use FastAPI with OpenAPI specs.

- `POST /analyze` — payload = AnalysisRequest → returns AnalysisResponse (signed)
- `POST /apply` — payload = { session_id, approved_changes, user_id, signature } → validates & triggers snapshot & write
- `GET /status` — health, model info, last_snapshot
- `POST /upload_datalog` — accept .csv or rusEFI log → returns DatalogSummary
- `GET /snapshots` — list snapshots; `POST /rollback` — rollback snapshot

Authentication: local HMAC with per-installation key. UI includes key generation.

---

# 10. UI / UX design (non-tuner)

Flow:
1. Install companion, run TunerStudio, open plugin.
2. First-run wizard: create VehicleProfile.
3. Upload datalog or connect live.
4. Click "Generate Base Tune" → deterministic generator runs → displays base map preview.
5. Optionally: click "Analyze Datalog" → model runs and returns recommendations.
6. Show per-cell heatmap, with tooltips explaining why change recommended.
7. Apply controls: per-cell approve / global apply with clamping.
8. Live monitor view: streaming telemetry, safety bar, enable auto-corrections.

Important UI details:
- All high-risk actions require multi-step confirmations.
- Show full audit trail for each change.
- Provide "Explain" button that asks the LLM to explain in layman's terms.

---

# 11. Live one‑session power ramp algorithm (detailed)

**Prerequisites**
- Wideband O2 calibrated
- Knock sensor functional & characterized
- Stable fuel pressure
- User in dyno mode or closed track
- Emergency stop available (hardware or software)

**Algorithm variables**
- `target_hp`
- `current_estimated_hp`
- `boost_step_kpa` (e.g., 5–10 kPa)
- `fuel_step_pct` (≤ 2% live)
- `timing_step_deg` (manual or advisory)
- `check_interval_s` (10–15s)
- `safety_thresholds` (knock_count, IAT_delta, AFR deviation)

**Procedure**
1. Generate conservative base map scaled for target_hp estimated boost.
2. Enter "Power Ramp Mode".
3. For each iteration:
   a. Increase boost by `boost_step_kpa`.
   b. Allow system to stabilize for `check_interval_s`.
   c. Monitor AFR, knock, injector duty, IAT, torque estimate.
   d. If torque increases and no safety triggered → continue.
   e. If safety triggered → revert last boost step, reduce boost, log warning, require manual review.
   f. Use fuel-only live corrections while holding boost (fuel-step ≤ 2% per check interval) to maintain AFR target.
4. Repeat until `current_estimated_hp >= target_hp` or safety cutoff reached.

**Torque estimation**
- Use instantaneous MAP × VE × RPM → estimate mass airflow → compute estimated HP using `HP ≈ airflow_lb_per_min × 10` (tuned constant).
- For better accuracy, combine with voltage-derived torque sensor if available or dyno feedback.

---

# 12. Logging, audit, rollback & forensics

- Every analysis response and every apply action must be snapshotted and logged in an append-only store with timestamp, user, session_id, pre/post calibration diffs, and HMAC signature.
- Snapshots are physically stored as `.bin` calibration files and indexed in SQLite DB.
- Rollback endpoint must validate ownership & create an audit entry.
- Provide exporters for CSV log history for compliance and review.

---

# 13. Security & signing

- Generate an installation HMAC keypair stored in OS-protected storage (Windows DPAPI recommended).
- Sign every AnalysisResponse with HMAC_SHA256 over canonical JSON.
- Plugin must verify signature before allowing apply.
- Default network binding: `localhost` only. If user enables remote, require explicit consent and PIN.

---

# 14. Testing plan & acceptance criteria

## Unit tests
- JSON schema validation for all endpoints
- Guardrail rule tests (knock, occupancy, clamp)
- Deterministic engine model numeric tests (injector scaling, VE smoothing)
- Snapshot & rollback tests

## Integration tests
- Simulated datalog sequences: low-load, mid-load, high-load, knock event
- End-to-end: generate base map, apply changes, verify snapshot, rollback

## Manual acceptance criteria (sample)
- A novice can complete Build Profile wizard and generate a base map that starts and idles within 3 attempts with no error codes (assuming correct sensors).
- Suggested Apply never modifies ignition unless user confirms explicit approval.
- Live auto-corrects maintain AFR within ±3% of target during test sweeps.

---

# 15. Deployment & ops (Windows-focused)

- Provide an installer (Inno Setup) that:
  - Installs Companion Service (as Windows service or UX app with background service).
  - Installs TunerStudio plugin / WebView assets.
  - Sets up local model environment (option to download models).
- Provide scripts (PowerShell) to download & verify model weights.
- Provide a "lite" mode for machines without GPU: fall back to smaller model or cloud.

---

# 16. Developer handoff checklist & milestones

**Milestone 1 — Core backend**
- FastAPI skeleton, DB, snapshot store, API endpoints stubs
- Deterministic engine model implemented with unit tests

**Milestone 2 — TunerStudio integration & UI**
- Web UI served locally
- Build Profile wizard + datalog uploader
- Table heatmap rendering

**Milestone 3 — Model integration**
- Model adapter (local runtime) + deterministic prompt & schema enforcement
- RAG retrieval for knowledge base

**Milestone 4 — Guardrails & applying**
- Implement guardrails and apply flow with snapshotting & HMAC
- Live auto-correct simulator

**Milestone 5 — Power ramp & live tests**
- Implement staged ramp + safety triggers; run closed-loop tests on dyno (manual step)

**Milestone 6 — QA & docs**
- Full test suite, user manual, emergency procedures

---

# 17. Appendix: practical formulas & examples

## Injector scaling example (simplified)
- Target HP 300 whp → estimate airflow ≈ HP × 0.8 (empirical) → ~240 lb/min (example constant)
- Use displacement & RPM to compute mass per cycle and required fuel mass for AFR; compute pulsewidth and injector scaling.

## VE smoothing kernel (3x3)
```
[ [0.0625, 0.125, 0.0625],
  [0.125,  0.25,  0.125 ],
  [0.0625, 0.125, 0.0625] ]
```

## Example vehicle profile (JSON)
(See `VehicleProfile` schema; example included for B-series 2.0L, E85, 1000cc injectors)

---

# Final notes & safety disclaimer
This document is a comprehensive engineering specification. It is intentionally conservative on safety-critical actions. The implementer must follow local legal rules and use a dyno or controlled environment for high-power tuning. The system should always err on the side of protecting the engine and user safety.

---

End of master spec.
