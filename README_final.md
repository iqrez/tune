# 🏎️ AI BaseTune Architect

**The ultimate local-first, safety-first companion for rusEFI ECUs.**

AI BaseTune Architect allows any car enthusiast—from beginner to expert—to tune their engine using natural language. It combines a professional-grade deterministic math engine with the power of a local LLM (Ollama) to provide a "ChatGPT for car tuning" experience that is safer and more precise than manual tuning.

---

## 🚀 Key Features

- **Natural Language Tuning**: "Safety-first" AI that understands your engine's needs.
- **rusEFI Native**: Full binary protocol support for real-time telemetry and tuning.
- **Deterministic Math Engine**: Every AI suggestion is cross-verified against engine physics.
- **Local-First**: 100% private. No data leaves your machine. Runs with Ollama.
- **Interactive UI**: Real-time gauges, visual vehicle profiles, and ChatGPT-style interaction.

---

## 🛠️ Installation

### 1. Requirements
- **Python 3.10+**
- **Ollama** (running locally with `llama3` or `codellama`)
- **rusEFI Console** (for simulation or hardware connection)

### 2. Setup
1. Clone this repository (or copy the folder).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure Ollama is running:
   ```bash
   ollama run llama3
   ```

---

## 🚦 How to Start

### Step 1: Start the Backend
Start the FastAPI server which handles the math, RAG, and ECU logic:
```bash
run_backend.bat
```

### Step 2: Start the UI
Launch the Gradio interface:
```bash
run_chat.bat
```
Open your browser to `http://localhost:7860`.

### Step 3: Connect to rusEFI
- Start your rusEFI hardware or the simulator (`java -jar rusefi_console.jar simulator`).
- In the UI, click **"Connect ECU"**.

---

## 💬 Example Conversations

- **User**: "I just installed ID1000 injectors and a GT3076 turbo on my B18C. Build me a safe base tune."
- **AI**: "Understood. I have calculated the new injector scaling (43.5 psi base) and generated a conservative ignition map for the GT3076 boost curve. Fuel targets are set to 11.5 AFR in boost for safety. Apply changes?"

- **User**: "Analyze my last pull and adjust the VE table."
- **AI**: "Analyzing logs... I found a 5% lean spike at 4500 RPM / 180 kPa. I recommend increasing the VE table by 4.2% in that zone. Other cells are within 1% of target. Apply patch?"

---

## ⚠️ Safety Warnings

> [!WARNING]
> Engine tuning involves significant mechanical risks. 
> 
> - **Always use a wideband sensor**: Never trust calculated values without real-time feedback.
> - **Conservative Timing**: The AI defaults to safe timing, but every engine is different. Listen for knock.
> - **Hardware Verification**: Always verify that the AI successfully 'burned' the changes before a high-load pull.

---

## 🏗️ Architecture

- **Frontend**: Gradio (Web UI) + Plotly (Gauges).
- **Backend**: FastAPI (Python).
- **ECU Interface**: rusEFI Binary Protocol (TCP/Serial).
- **Core**: Deterministic Math Engine + Local LLM RAG.

---

*Developed by AI BaseTune Architect Team. Local-first, Safety-first.*
