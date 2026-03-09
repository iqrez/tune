# AI BaseTune Coding Agent — Supplemental Dataset Plan
**Supplemental Datasets and Sourcing Instructions for B-series and D-series LS VTEC Builds**

Version: 1.0 — Companion to AI BaseTune Coding Agent Instruction Guide

---

## 1. Sensor & Engine Physics Data

**Objective:** Provide the AI with accurate responses to knock, temperature, and manifold pressure variations.

| Dataset | Source | Format | Notes |
|---------|--------|--------|-------|
| Knock sensor response tables | rusEFI public logs, tuners' shared datasets | .CSV/.LOG | Include RPM vs knock threshold per fuel type. |
| Intake Air Temp (IAT) & Coolant Temp (ECT) vs AFR/VE | Dyno logs, Megasquirt logs | .CSV/.LOG | Annotated with load/RPM for AI correlation. |
| Manifold Absolute Pressure (MAP) vs RPM vs VE | Logged vehicle data or forum submissions | .CSV/.LOG | Critical for load-dependent VE adjustments. |

**Coding Agent Instructions:** Download public logs from rusEFI, MegaLogViewer archives, and any shared forum logs. Convert to structured CSV and store in `/data/sensors/LSVTEC/`.

---

## 2. Dyno & Road-Test Performance Data

**Objective:** Teach AI cause-effect between table changes and HP/TQ outcomes.

| Dataset | Source | Format | Notes |
|---------|--------|--------|-------|
| Dyno runs with VE/fuel/ignition tables | rusEFI public logs, tuner blogs/forums | .LOG, .CSV | Include RPM, AFR, boost, VE, ignition. |
| Acceleration & throttle response data | Shared tuners' logs | .LOG | Sequence data for real-world engine response. |
| Turbo spool & boost response | Tuner logs, forums | .LOG, .CSV | Useful for turbo LS VTEC builds. |

**Instructions:** Convert logs to JSON/CSV format and index in `/data/logs/LSVTEC/` for RAG.

---

## 3. Injector, Fuel, and Turbo Specifications

| Dataset | Source | Format | Notes |
|---------|--------|--------|-------|
| Injector deadtime vs voltage & pulsewidth | RC Fuel Injection charts, injectordata.com | .CSV | Include for all injectors used in B/D series builds. |
| Fuel pressure response | Manufacturer datasheets | .CSV | AFR vs pressure adjustments. |
| Turbo compressor maps | Garrett/Precision/TurboMak | .PDF/.CSV | Include max airflow, efficiency, and surge lines. |

**Instructions:** Download manufacturer PDFs, convert to CSV or JSON. Organize by engine/family: `/data/injectors/B18C/`, `/data/turbos/B18C/`.

---

## 4. Historical Tuning Adjustments

**Objective:** Show AI iterative tuning patterns and safe/unsafe cases.

| Dataset | Source | Format | Notes |
|---------|--------|--------|-------|
| Base map iterations | Tuners' logs, forums | .BIN/.MSQ/.S3D | Include multiple stages of tuning per engine. |
| Failure case logs | Forum threads, dyno logs | .LOG | Annotated with lean/knock/overboost events. |

**Instructions:** Store per engine: `/data/historical/B18C_LSVTEC/`. Annotate failures for guardrail training.

---

## 5. Environmental Data

| Dataset | Source | Format | Notes |
|---------|--------|--------|-------|
| Altitude vs VE/AFR impact | Public dyno/test logs, tuners' notes | .CSV | Include multiple altitudes for safe AFR adjustments. |
| Temperature vs VE/AFR | Test logs, tuners' shared data | .CSV | Store as environmental correction tables. |

**Instructions:** Index into RAG database as supplemental reference.

---

## 6. Tuning Reference Guides & Calculators

| Dataset | Source | Format | Notes |
|---------|--------|--------|-------|
| EFI tuning manuals | Hondata, Megasquirt, rusEFI public wikis | PDF/HTML | Include content on injector sizing, fuel trims, VTEC transitions. |
| VE/Fuel/Ignition calculators | Public spreadsheets or JSON | .CSV/.JSON | Convert formulas to structured format for AI reference. |

**Instructions:** Store manuals in `/data/manuals/LSVTEC/` and calculators in `/data/calculators/LSVTEC/`. Include prompts for AI to reference formulas safely.

---

## 7. Coding Agent Tasks for Supplemental Datasets

1. **Locate and download** all publicly available logs, PDFs, charts, and shared tuning datasets.  
2. **Filter** for LS VTEC B-series and D-series engines first.  
3. **Organize** datasets into structured folders by engine/family and dataset type:  
   - `/data/sensors/LSVTEC/`  
   - `/data/logs/LSVTEC/`  
   - `/data/injectors/B18C/`  
   - `/data/turbos/B18C/`  
   - `/data/historical/B18C_LSVTEC/`  
   - `/data/manuals/LSVTEC/`  
   - `/data/calculators/LSVTEC/`  
4. **Convert** all raw logs or charts into structured CSV/JSON where possible for RAG indexing.  
5. **Annotate** failure cases and guardrail thresholds to ensure AI generates safe recommendations.  
6. **Integrate** these supplemental datasets with the main ECU maps, logs, and LoRA fine-tuning workflow outlined in the primary instruction guide.

---

**End of Supplemental Dataset Plan**

*Prepared for professional coding agents to fully augment AI-assisted tuning for Honda B-series and D-series LS VTEC engines, ensuring safe, robust, and informed table generation.*
