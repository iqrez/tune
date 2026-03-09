
# AI BaseTune Coding Agent — Complete Instruction Guide
**Training, Deployment, and Dataset Sourcing for B-series and D-series Hondas (Focus on LS VTEC)**
Version: 2.0 — Professional Instruction Guide for Implementation

---

## 1. Objective

- Train a **domain-specialized LLM** to generate safe base fuel, ignition, VE, and boost maps for B-series and D-series Honda engines.
- Primary focus: **LS VTEC builds**.
- Ensure the trained model can run **offline on a Raspberry Pi 5 (4 GB RAM)** using a **3B quantized model with LoRA**.
- Integrate deterministic engine math and guardrails to ensure safe tuning.
- Include **dataset sourcing and organization instructions** so the agent can retrieve all required materials.

---

## 2. Model Selection

- **Base Model Options**:
  - **GPT4All-J 3B**: Open-source, instruction-following, 4-bit quantized.
  - **MPT-7B-Instruct** (pruned to ~3B): 4-bit quantized for Pi 5 deployment.
- **Runtime**: `llama.cpp`, `vLLM`, or Ollama local container.
- **Fine-tuning Method**: LoRA / PEFT for small-memory adaptation.

**Goal**: Keep runtime memory < 2 GB for LLM, leaving room for companion service and OS.

---

## 3. Dataset Creation

### 3.1 Vehicle Profile Schema

Each record should include:

```json
{
  "engine_family": "B-series",
  "engine_model": "B18C LS VTEC",
  "displacement_l": 1.8,
  "cylinders": 4,
  "aspiration": "NA|Turbo",
  "compression_ratio": 11.1,
  "fuel_type": "93 Octane",
  "injector_cc_min": 550,
  "turbo_model": null,
  "wastegate_type": null,
  "redline_rpm": 8800,
  "notes": "Street LS VTEC, conservative tune"
}
```

### 3.2 Maps

- **VE table**: 2D RPM × Load table; initial guess 0.7–0.85, smoothed.
- **Fuel table (AFR targets)**:
  - Idle: 14.0–14.5
  - Cruise: 14.2–14.8
  - Boost / high load: 11.0–12.5
- **Ignition table**: conservative MBT baseline minus safety margin; boost/NA correction applied.
- **Boost table**: linear ramp to target boost; safety clamp applied.

### 3.3 Data Sources (Coding Agent Instructions)

The agent should download or source the following public/open datasets for B-series and D-series engines:

**1. ECU ROMs and Basemaps**

| Source | Format | Engines Covered | Notes |
|--------|--------|----------------|-------|
| Hondabase GitHub | .BIN, .ROM | B16A, B18B, B18C, B20B, D16Z6 | Publicly maintained ECU dumps. Can be opened with Hondata Crome/Neptune or MegaSquirt tools. |
| Hondata S300 Basemaps | .S3D | B16A, B18A/B/C, B20, D16Z6 | Stock and custom base maps. Prioritize LS VTEC builds. |
| Megasquirt/Speeduino Base Maps | .MSQ, .INI | B16A, B18C, B20B, D16 SOHC/DOHC | Can be imported into TunerStudio. Includes initial tuning tables for EFI. |
| rusEFI public database | .MAP, .LOG | LS/VTEC builds, B18, B20 | Includes user-uploaded maps and logs with AFR, VE, ignition data. |

**2. Dyno Logs / Real-World Data**

- Extract from rusEFI shared logs (.LOG) for LS VTEC setups: includes RPM, load, AFR, boost, VE, and ignition tables.
- Tools like **MegaLogViewer HD** can process logs from MegaSquirt or Speeduino systems to extract VE/fuel/ignition trends.
- Injector specs: RC Fuel Injection charts, injectordata.com, community spreadsheets.
- Turbo specifications: Garrett, Precision, or TurboMak compressor maps.

**3. Community Repositories & Forums**

- **Hondabase GitHub** – ECU ROMs, documentation, component databases.
- **PGMFI/Grassroots ECU Wiki** – Stock ECU ID codes and bin files for OBD0/1 Hondas.
- **Honda Tuning Suite Wiki** – Confirm engine families and required stock maps.
- Forums: Honda-Tech, TSX/Integra.org, Reddit r/Honda – for shared base maps, tuning advice, dyno screenshots. Use legally posted content only.

**Instruction for Coding Agent:**

1. Download all publicly available ROMs, basemaps, and MSQ files for LS VTEC, B16, B18, B20, D16 engines.
2. Store in structured folders per engine type: `/data/ROMs/B18C_LS_VTEC/`, `/data/Msq/B16A/`, etc.
3. Extract VE, fuel, ignition, and boost tables into **CSV or JSON** for RAG indexing and LoRA fine-tuning.
4. Download dyno logs and annotate AFR, boost, VE, ignition trends. Store as `/data/logs/LSVTEC/`.
5. Ensure all sources are **publicly accessible or legally shared**. Avoid copyrighted or proprietary content unless permission is granted.

---

## 4. Data Formatting for LLM

- Use **JSON structured inputs**: VehicleProfile + BaseMap + Notes + Optional DatalogSummary.
- **Output labels**: delta_fuel_pct, delta_ign_deg, confidence, reasoning/explanation.
- LoRA fine-tuning dataset: instruction-response pairs for supervised learning.

**Example pair**:

```json
{
  "instruction": "Generate safe base VE, fuel, ignition tables for a B18C LS VTEC NA, 93 octane, 550cc injectors, redline 8800",
  "input": { ... VehicleProfile JSON ... },
  "output": { ... VE, fuel, ignition tables + explanations ... }
}
```

---

## 5. Fine-Tuning Procedure

### 5.1 Environment Setup

```bash
conda create -n aitune python=3.10
conda activate aitune
pip install torch torchvision transformers peft datasets
```

- Use desktop GPU with ≥16 GB VRAM for training.
- Store LoRA weights separately (e.g., `bseries_dseries_lora.pt`).
- Test merged LoRA + base model locally before Pi deployment.

### 5.2 Training Hyperparameters (suggested)

- Batch size: 4–8
- Learning rate: 1e-4
- Epochs: 3–5
- Max tokens: 1024–2048
- Optimizer: AdamW or Lion

---

## 6. Integration with RAG

- Store engine families, VE/fuel curves, injector data, turbo flow tables, AFR targets in **local vector DB**.
- Runtime steps:
  1. Query top 5–10 relevant documents per build.
  2. Inject into prompt for LLM.
  3. LLM produces safe per-cell recommendations, respecting guardrails.

- Pi 5 compatible DB options: FAISS-lite, Chroma, or embedded SQLite vector math.

---

## 7. Deterministic Engine Model

**Coding agent must implement independently. LLM suggestions are advisory.**

1. **Injector scaling**: pulsewidth = required fuel / flow + deadtime.
2. **VE table**: smooth baseline grid, initial guess 0.7–0.85.
3. **AFR targets**: depends on fuel type and load.
4. **Ignition table**: MBT baseline minus safety margin; adjust for boost.
5. **Boost table**: linear ramp, clamped to safe target.
6. **Guardrails**: injector duty ≤85%, ignition limits, knock/AFR/IAT monitoring.

---

## 8. Testing and Validation

1. **Unit tests**: JSON schema validation, map generation sanity checks.
2. **Simulation tests**: feed historical datalogs; check for safety and plausible outputs.
3. **Dyno / bench validation**: ensure base tune starts, idles, and maintains safe AFRs.
4. **Safety tests**: emergency rollback, fuel-only auto corrections.

---

## 9. Deployment on Raspberry Pi 5

- Install quantized model + LoRA weights.
- Install companion service (Python/FastAPI) + deterministic engine math.
- Copy RAG vector store.
- Test offline LLM reasoning + VE/fuel/ignition recommendations.
- Optional: connect to TunerStudio WebView for UI display.

### Memory Allocation Targets

| Component | RAM estimate |
|-----------|-------------|
| OS + Pi services | 1 GB |
| Quantized LLM + LoRA | 1–1.5 GB |
| Companion Service + RAG | 0.5–0.8 GB |
| Headroom | 0.2–0.5 GB |

---

## 10. Prioritization Strategy

- LS VTEC B-series builds: primary focus.
- D-series engines: secondary focus.
- Include variations: NA, turbo, street vs track.
- Ensure dataset includes **safety margins and knock prevention knowledge**.
- Ensure coding agent downloads all source datasets before starting fine-tuning.

---

**End of Complete Instruction Guide**

*Prepared for use by professional coding agents to implement AI-assisted base tuning for Honda B-series and D-series engines, focusing on LS VTEC builds, with offline Pi 5 deployment, including all dataset sourcing instructions.*
