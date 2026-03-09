import gradio as gr
import plotly.graph_objects as go
import pandas as pd
import json
import requests
import os

# --- Backend Configuration ---
def get_backend_url():
    port = 8000
    try:
        # Check for .port file in parent directory
        port_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".port")
        if os.path.exists(port_file):
            with open(port_file, "r") as f:
                port = int(f.read().strip())
    except Exception:
        pass
    return f"http://localhost:{port}/api/v1"

BACKEND_URL = get_backend_url()

def _handle_param_change(value, param_name, state):
    """
    Generic handler for parameter changes.
    Updates the backend and local state.
    """
    if not param_name:
        return state
    
    try:
        # 1. Write to backend
        write_val = value
        if isinstance(value, pd.DataFrame):
            write_val = value.values.tolist()
            
        requests.post(
            f"{BACKEND_URL}/parameters/write",
            json={"name": param_name, "value": write_val, "burn_after": False},
            timeout=5
        )
        
        # 2. Update local state copy
        if state and "parameters" in state:
            found = False
            for p in state.get("parameters", []):
                if p.get("name") == param_name or (p.get("aliases") and param_name in p.get("aliases", [])):
                    p["value"] = write_val
                    found = True
                    break
            if not found:
                state.setdefault("parameters", []).append({"name": param_name, "value": write_val})
            
    except Exception as e:
        print(f"Exception writing {param_name}: {e}")
        
    return state

def _handle_burn(state):
    """Calls the burn API to persist changes to ECU flash."""
    try:
        resp = requests.post(f"{BACKEND_URL}/parameters/burn", json={}, timeout=10)
        if resp.status_code == 200:
            return "Burn Successful: Changes persisted to flash."
        return f"Burn Failed: {resp.text}"
    except Exception as e:
        return f"Burn Exception: {e}"

# --- UI Helpers for TunerStudio Replica ---

def _get_param(state: dict, name_or_alias: str) -> dict:
    """Helper to find a parameter by name or alias in the full_tuning_state."""
    if not state or "parameters" not in state:
        return {}
    params = state["parameters"]
    q = name_or_alias.lower()
    # Direct match
    for p in params:
        if p.get("name", "").lower() == q:
            return p
    # Alias match
    for p in params:
        for alias in p.get("aliases", []):
            if alias.lower() == q:
                return p
    return {}

def _ts_header(title: str):
    gr.Markdown(f"### {title}")

def _ts_label(text: str, is_red=False, is_blue=False):
    classes = []
    if is_red: classes.append("ts-red-banner")
    if is_blue: classes.append("ts-blue-banner")
    if not is_red and not is_blue: classes.append("ts-label")
    gr.Markdown(text, elem_classes=classes)

def _ts_number(label: str, param_name: str, state: dict, ghosted=False, precision=2):
    p = _get_param(state, param_name)
    val = p.get("value", 0.0) if p else 0.0
    units = p.get("units", "") if p else ""
    with gr.Row(elem_classes="ts-row"):
        _ts_label(f"{label} ({units})" if units else label)
        num = gr.Number(value=val, precision=precision, show_label=False, elem_classes=["ts-input"], interactive=not ghosted)
    
    # Interaction
    name_state = gr.State(param_name)
    num.submit(_handle_param_change, inputs=[num, name_state, state], outputs=[state])
    num.blur(_handle_param_change, inputs=[num, name_state, state], outputs=[state])
    return num

def _ts_dropdown(label: str, param_name: str, state: dict, choices: list = None, ghosted=False):
    p = _get_param(state, param_name)
    val = str(p.get("value", "")) if p else ""
    if choices is None:
        choices = p.get("options", []) if p else [val]
    
    # Ensure val is in choices for Gradio
    if val not in choices and val is not None:
        choices = [val] + choices

    with gr.Row(elem_classes="ts-row"):
        _ts_label(label)
        dd = gr.Dropdown(choices=choices, value=val, show_label=False, elem_classes=["ts-input"], interactive=not ghosted)
    
    # Interaction
    name_state = gr.State(param_name)
    dd.change(_handle_param_change, inputs=[dd, name_state, state], outputs=[state])
    return dd

def _ts_text(label: str, param_name: str, state: dict, ghosted=False):
    p = _get_param(state, param_name)
    val = str(p.get("value", "")) if p else ""
    with gr.Row(elem_classes="ts-row"):
        _ts_label(label)
        txt = gr.Textbox(value=val, show_label=False, elem_classes=["ts-input"], interactive=not ghosted)
    
    # Interaction
    name_state = gr.State(param_name)
    txt.submit(_handle_param_change, inputs=[txt, name_state, state], outputs=[state])
    txt.blur(_handle_param_change, inputs=[txt, name_state, state], outputs=[state])
    return txt

def _render_screen_by_name(selected_node: str, state: dict):
    """Routing based on the tree node name or ID."""
    if selected_node == "vehicleInfo":
        _render_vehicle_info(state)
    elif selected_node in ["revLimiters", "revLimit", "hardLimits"]:
        _render_limits_fallbacks(state)
    elif selected_node in ["LowOilPressure", "lowOilPressure"]:
        _render_low_oil_pressure(state)
    elif selected_node in ["HighOilPressure", "highOilPressure"]:
        _render_high_oil_pressure(state)
    elif selected_node == "triggerHardware":
        _render_trigger(state)
    elif selected_node in ["advancedTrigger", "triggerAdvanced"]:
        _render_advanced_trigger(state)
    elif selected_node == "triggerGapOverride":
        _render_trigger_gap_override(state)
    elif selected_node in ["battery", "batteryAlternator"]:
        _render_battery_alternator(state)
    elif selected_node == "ignitionKey":
        _render_ignition_key(state)
    elif selected_node == "ignitionAdvance":
        _render_ignition_advance(state)
    elif selected_node == "afrTarget":
        _render_afr_target(state)
    elif selected_node == "statusLeds":
        _render_status_leds(state)
    elif selected_node in ["outputs", "Outputs"]:
        _render_outputs(state)
    elif selected_node in ["cylinders", "cylinderBanks"]:
        _render_cylinder_banks(state)
    elif selected_node == "veTable1":
        _render_ve_table_3d(state)
    elif selected_node in ["veTable2", "veTable2D"]:
        _render_ve_table_2d(state)
    elif selected_node == "mapSensor":
        _render_map_sensor(state)
    elif selected_node == "tpsSensor":
        _render_tps_sensor(state)
    elif selected_node in ["iatSensor", "cltSensor", "fuelTempSensor", "oilTempSensor", "ambientTempSensor", "cdtSensor"]:
        _render_thermistor(selected_node, state)
    elif selected_node == "idleSettings":
        _render_idle_settings(state)
    elif selected_node == "injectorDeadTime":
        _render_injector_dead_time(state)
    else:
        # Generic fallback
        _render_generic_scalar(selected_node, state)

def render_dialog_content(selected_node: str, state: dict):
    if not selected_node:
        gr.Markdown("Select a parameter from the tree.")
        return

    with gr.Column(elem_classes="ts-dialog-window"):
        # Status header
        status_msg = gr.Markdown("Ready", elem_classes="ts-dialog-status-msg")
        
        with gr.Row():
            with gr.Column(scale=4, elem_classes="ts-dialog-body"):
                _render_screen_by_name(selected_node, state)
            
            with gr.Column(scale=2, elem_classes="ts-dialog-sidebar"):
                 _ts_header("Live Data")
                 gr.Plot(label="Gauges", elem_classes="ts-bg-dark")
                 gr.Markdown("Right-click for more diagnostics", elem_classes="muted")

        # Footer
        with gr.Row(elem_classes="ts-dialog-footer"):
            burn_btn = gr.Button("Burn (🔥)", variant="primary", scale=1)
            gr.Button("Undo", scale=1)
            gr.Button("Redo", scale=1)
            close_btn = gr.Button("Close", variant="secondary", scale=1)
            
        # Dialog level interactions
        burn_btn.click(_handle_burn, inputs=[state], outputs=[status_msg])
        close_btn.click(lambda: "Dialog closed. Select another item.", outputs=[status_msg])

# --- Screen Implementations ---

def _render_vehicle_info(state: dict):
    _ts_header("Vehicle Information")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Vehicle Information")
        _ts_number("Number of cylinders", "cylindersCount", state)
        _ts_number("Displacement(L)", "engineDisplacement", state, precision=3)
        _ts_dropdown("Firing order", "firingOrder", state, choices=["1-3-4-2", "1-5-3-6-2-4"])
        _ts_dropdown("Tuning View", "tuningView", state, choices=["Full", "Basic"])
        _ts_dropdown("Lambda display", "lambdaDisplay", state, choices=["AFR", "Lambda"])
        _ts_label("After changing this configuration, it is recommended to create a new project due to a limitation in TS.", is_red=True)
        _ts_dropdown("Temperature/Pressure display", "unitsDisplay", state, choices=["Metric", "Imperial"])
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Engine Metadata")
        _ts_label("These metadata are used by rusEFI Online", is_blue=True)
        _ts_text("Engine Make", "engineMake", state)
        _ts_text("Manufacturer Engine Code", "engineCode", state)
        _ts_text("Vehicle Name", "vehicleName", state)
        _ts_text("VIN", "vin", state)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Fuel")
        _ts_label("https://rusefi.com/s/fuel", is_red=True)
        _ts_dropdown("Fuel strategy", "fuelAlgorithm", state)
    gr.Markdown("Number of cylinder the engine has.", elem_classes="muted")

def _render_limits_fallbacks(state: dict):
    _ts_header("Limits and fallbacks")
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Limits")
                _ts_dropdown("Cut fuel on RPM limit", "cutFuelOnHardLimit", state)
                _ts_dropdown("Cut spark on RPM limit", "cutSparkOnHardLimit", state)
                _ts_dropdown("Use Engine Temperature RPM limit curve", "useRpmLimitCurve", state)
                _ts_number("RPM hard limit(rpm)", "rpmHardLimit", state, precision=0)
                _ts_number("RPM limit hysteresis(RPM)", "rpmLimitHysteresis", state, precision=0)
                _ts_number("Boost cut pressure(kPa)", "boostCutPressure", state)
                _ts_number("Boost cut pressure hysteresis(kPa)", "boostCutPressureHysteresis", state, precision=1)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Injector Duty Cycle Limiter")
                _ts_number("Instantaneous injector duty cycle limit(%)", "maxInjectorDutyCycle", state)
                _ts_number("Sustained injector duty cycle limit(%)", "sustainedInjectorDutyCycle", state)
                _ts_number("Sustained injector duty cycle delay(sec)", "sustainedInjectorDutyCycleDelay", state)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Soft RPM Limit")
                _ts_number("Timing retard(deg)", "softLimitRetard", state)
                _ts_number("Fuel added(%)", "softLimitFuel", state)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Electronic Throttle Limiting")
                _ts_label("Smoothly close the throttle to limit RPM.")
                _ts_number("Soft limiter start(rpm)", "etbSoftLimitStart", state)
                _ts_number("Soft limiter range(rpm)", "etbSoftLimitRange", state)
        with gr.Column(scale=1):
            gr.Plot(label="Engine Temperature RPM Limit", elem_classes="ts-bg-dark")
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x5</div>")
    gr.Markdown("When enabled, this option cuts the fuel supply when the RPM limit is reached...", elem_classes="muted")

def _render_low_oil_pressure(state: dict):
    _ts_header("Low oil pressure protection")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_dropdown("Enable low oil pressure protection", "lowOilPressureProtection", state)
        _ts_number("Minimum oil pressure after start(kPa)", "lowOilPressureThreshold", state)
        _ts_number("Low oil pressure protection timeout(sec)", "lowOilPressureTimeout", state)
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="Min pressure vs RPM", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

def _render_high_oil_pressure(state: dict):
    _ts_header("High oil pressure protection")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_number("High oil pressure protection timeout(sec)", "highOilPressureTimeout", state)
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="Max pressure vs RPM", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x5</div>")

def _render_trigger(state: dict):
    _ts_header("Trigger")
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Primary Trigger")
                _ts_dropdown("Strokes", "engineCycle", state, choices=["Four Stroke", "Two Stroke"])
                _ts_dropdown("Trigger type", "triggerType", state)
                _ts_label("Reminder that 4-stroke cycle is 720 degrees", is_red=True)
                _ts_label("For well-known trigger types use '0' trigger angle offset", is_red=True)
                _ts_number("Trigger Angle Advance(deg btdc)", "triggerAngle", state)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_dropdown("Crank Sensor (Primary channel)", "triggerInputPin", state)
                _ts_dropdown("Primary Edge", "triggerInputEdge", state, choices=["Rising", "Falling"])
                _ts_dropdown("Secondary channel", "triggerSecondaryPin", state)
                _ts_dropdown("Secondary Edge", "triggerSecondaryEdge", state, choices=["Rising", "Falling"])
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Cam Inputs")
                _ts_label("https://rusefi.com/s/vvt", is_red=True)
                _ts_dropdown("Cam mode (intake)", "vvtMode", state)
                _ts_dropdown("Cam mode (exhaust)", "vvtMode2", state)
                _ts_dropdown("Cam sensor bank 1 intake", "vvtInputPin", state)
                _ts_dropdown("Cam sensor bank 1 exhaust", "vvtInputPin2", state)
                _ts_dropdown("Cam sensor bank 2 intake", "vvtInputPin3", state)
                _ts_dropdown("Cam sensor bank 2 exhaust", "vvtInputPin4", state)
                _ts_dropdown("intake Cam Edge Select", "vvtEdge1", state, choices=["Rising", "Falling"])
                _ts_dropdown("exhaust Cam Edge Select", "vvtEdge2", state, choices=["Rising", "Falling"])
                _ts_label("Set offset so VVT indicates 0 degrees in default position", is_blue=True)
                _ts_number("VVT offset bank 1 intake(value)", "vvtOffset", state)
                _ts_number("VVT offset bank 1 exhaust(value)", "vvtOffset2", state)
                _ts_number("VVT offset bank 2 intake(value)", "vvtOffset3", state)
                _ts_number("VVT offset bank 2 exhaust(value)", "vvtOffset4", state)
                _ts_dropdown("Cam for engine sync resolution", "syncResolution", state)

def _render_advanced_trigger(state: dict):
    _ts_header("Advanced Trigger")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Advanced Trigger")
        _ts_dropdown("Require cam/VVT sync for ignition", "requireSync", state)
        _ts_dropdown("Cam sync crank revolution", "syncRevolution", state)
        _ts_number("Maximum cam/VVT sync RPM(rpm)", "maxSyncRpm", state)
        _ts_dropdown("Enable noise filtering", "enableNoiseFiltering", state)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Console Logging")
        _ts_dropdown("Print verbose VVT sync details to console", "verboseVvt", state)
        _ts_dropdown("Print verbose trigger sync to console", "verboseTrigger", state)
        _ts_dropdown("Display logic signals", "displayLogicSignals", state)
        _ts_dropdown("Do not print messages in case of sync error", "hideSyncErrors", state)
        _ts_dropdown("Focus on inputs in engine sniffer", "snifferFocusInputs", state)

def _render_trigger_gap_override(state: dict):
    _ts_header("Trigger Gap Override")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Trigger Gap Override")
        _ts_label("This is a pretty advanced feature for when you are debugging trigger synchronization", is_red=True)
        _ts_dropdown("Override well known trigger gaps", "overrideTriggerGaps", state)
        _ts_number("gapTrackingLengthOverride(count)", "gapTrackingLength", state)
        _ts_dropdown("Override well known VVT gaps", "overrideVvtGaps", state)
        _ts_number("gapVvtTrackingLengthOverride(count)", "gapVvtTrackingLength", state)

def _render_battery_alternator(state: dict):
    _ts_header("Battery and Alternator Settings")
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Alternator Settings")
                _ts_dropdown("Enabled", "alternatorControlEnabled", state)
                _ts_dropdown("Control output", "alternatorOutputPin", state)
                _ts_dropdown("Control output mode", "alternatorControlMode", state)
                _ts_number("PWM frequency(Hz)", "alternatorPwmFrequency", state)
                _ts_number("A/C duty adder(%)", "acDutyAdder", state)
                _ts_label("PID control", is_blue=True)
                _ts_number("P term", "alternatorPidP", state)
                _ts_number("I term", "alternatorPidI", state)
                _ts_number("D term", "alternatorPidD", state)
                _ts_label("% duty = Pterm + Iterm + Dterm + offset%", is_blue=True)
        with gr.Column(scale=1):
            gr.HTML("<div>Table editor placeholder target voltage 2D</div>")

def _render_ignition_key(state: dict):
    _ts_header("Ignition key input Settings")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_label("Only for advanced power externalWiring management wiring", is_red=True)
        _ts_dropdown("Ignition Key ADC input", "ignitionKeyAdcPin", state)
        _ts_number("Ignition Key ADC Divider", "ignitionKeyAdcDivider", state)

def _render_ignition_advance(state: dict):
    _ts_header("Ignition Advance")
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Ignition Timing")
                _ts_dropdown("Ignition mode", "ignitionMode", state)
                _ts_dropdown("Ignition output", "ignitionOutput", state)
                _ts_number("Base timing(deg)", "baseTiming", state)
                _ts_number("Cranking advance(deg)", "crankingAdvance", state)
                _ts_number("Idle advance(deg)", "idleAdvance", state)
                _ts_number("Rev limit advance(deg)", "revLimitAdvance", state)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Dwell Control")
                _ts_number("Dwell time(ms)", "dwellTime", state)
                _ts_number("Dwell time cranking(ms)", "dwellTimeCranking", state)
                _ts_number("Dwell time min(ms)", "dwellTimeMin", state)
                _ts_number("Dwell time max(ms)", "dwellTimeMax", state)
        with gr.Column(scale=1):
            gr.Plot(label="Ignition Advance Table", elem_classes="ts-bg-dark")
            gr.Plot(label="Dwell Time vs Voltage", elem_classes="ts-bg-dark")

def _render_status_leds(state: dict):
    _ts_header("Status LEDs")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_dropdown("Trigger error LED", "triggerErrorPin", state)
        _ts_dropdown("Debug Trigger Sync", "debugTriggerSyncPin", state)

def _render_afr_target(state: dict):
    _ts_header("AFR Target")
    with gr.Row():
        with gr.Column(scale=1):
            _ts_table("AFR Target Table", "afrTable", state)
        with gr.Column(scale=1):
            p = _get_param(state, "afrTable")
            val = p.get("value", [[]])
            if val and isinstance(val[0], list):
                fig = go.Figure(data=[go.Surface(z=val)])
                fig.update_layout(
                    margin=dict(l=0, r=0, b=0, t=0),
                    scene=dict(xaxis_title='RPM', yaxis_title='MAP', zaxis_title='AFR'),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color="white")
                )
                gr.Plot(fig, label="3D Surface")
            else:
                gr.Markdown("No 3D data available")

def _ts_table(label: str, param_name: str, state: dict):
    p = _get_param(state, param_name)
    val = p.get("value", [[]]) if p else [[]]
    rows = p.get("rows", 1)
    cols = p.get("cols", 1)
    x_axis = p.get("x_axis", [])
    y_axis = p.get("y_axis", [])
    
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header(label)
        # Use Dataframe for table editing
        df = gr.Dataframe(
            value=val,
            row_count=rows,
            col_count=cols,
            interactive=True,
            show_label=False,
            elem_classes=["ts-table-editor"],
        )
        if x_axis or y_axis:
            gr.Markdown(f"Axes: X={len(x_axis)} pts, Y={len(y_axis)} pts", elem_classes="muted")
    return df

def _render_outputs(state: dict):
    _ts_header("Outputs")
    # Using generic fallback for massive output mapping momentarily
    _render_generic_scalar("Outputs", state)

def _render_cylinder_banks(state: dict):
    _ts_header("Cylinder Banks")
    with gr.Group(elem_classes="ts-fieldset"):
        # Mapping cylindersCount if possible, or just standard 16
        count = int(_get_param(state, "cylindersCount").get("value", 8))
        for i in range(1, 13):
            _ts_number(f"Cylinder {i}", f"cylinderBankSelect{i}", state, ghosted=(i > count))

def _render_ve_table_3d(state: dict):
    _ts_header("VE Table (3D)")
    with gr.Row():
        with gr.Column(scale=1):
            _ts_table("VE Table 1", "veTable1", state)
        with gr.Column(scale=1):
            p = _get_param(state, "veTable1")
            val = p.get("value", [[]])
            if val and isinstance(val[0], list):
                fig = go.Figure(data=[go.Surface(z=val)])
                fig.update_layout(
                    margin=dict(l=0, r=0, b=0, t=0),
                    scene=dict(xaxis_title='RPM', yaxis_title='MAP', zaxis_title='VE'),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color="white")
                )
                gr.Plot(fig, label="3D Surface")
            else:
                gr.Markdown("No 3D data available")

def _render_ve_table_2d(state: dict):
    _ts_header("VE (2D Table Editor)")
    _ts_table("VE Table 2 (2D)", "veTable2", state)

def _render_map_sensor(state: dict):
    _ts_header("MAP Sensor Calibration")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("MAP Sensor Settings")
                _ts_dropdown("MAP Sensor Type", "mapSensorType", state)
                _ts_number("MAP Sensor Offset(kPa)", "mapSensorOffset", state)
                _ts_number("MAP Sensor Multiplier", "mapSensorMultiplier", state)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("MAP Sensor Calibration Points")
                _ts_number("Low Pressure(kPa)", "mapLowPressure", state)
                _ts_number("Low Voltage(V)", "mapLowVoltage", state)
                gr.HTML("<hr style='margin:10px 0; border-color:#444;'/>")
                _ts_number("High Pressure(kPa)", "mapHighPressure", state)
                _ts_number("High Voltage(V)", "mapHighVoltage", state)
        with gr.Column(scale=1):
            gr.Plot(label="Transfer Curve", elem_classes="ts-bg-dark")
            gr.Plot(label="Current Value", elem_classes="ts-bg-dark")

def _render_tps_sensor(state: dict):
    _ts_header("TPS Sensor Calibration")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("TPS Sensor Settings")
                _ts_dropdown("TPS Sensor Type", "tpsSensorType", state)
                _ts_dropdown("TPS Sensor Input", "tpsSensorInput", state)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("TPS Sensor Calibration Points")
                _ts_number("Closed Throttle Voltage(V)", "tpsClosedVoltage", state)
                _ts_number("Open Throttle Voltage(V)", "tpsOpenVoltage", state)
        with gr.Column(scale=1):
            gr.Plot(label="Transfer Curve", elem_classes="ts-bg-dark")
            gr.Plot(label="Current Value", elem_classes="ts-bg-dark")

def _render_idle_settings(state: dict):
    _ts_header("Idle Settings")
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Idle Control")
                _ts_dropdown("Idle control mode", "idleControlMode", state)
                _ts_number("Target idle RPM(rpm)", "targetIdleRpm", state)
                _ts_number("Idle RPM hysteresis(rpm)", "idleRpmHysteresis", state)
                _ts_number("Idle valve frequency(Hz)", "idleValveFrequency", state)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Idle PID Control")
                _ts_number("P term", "idlePidP", state)
                _ts_number("I term", "idlePidI", state)
                _ts_number("D term", "idlePidD", state)
        with gr.Column(scale=1):
            gr.Plot(label="Idle Target RPM vs CLT", elem_classes="ts-bg-dark")
            gr.Plot(label="Idle Valve Position vs CLT", elem_classes="ts-bg-dark")

def _render_injector_dead_time(state: dict):
    _ts_header("Injector dead time")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_number("Injector dead time at 14 volts(ms)", "injectorDeadTime", state, precision=3)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_table("Injector Lag Voltage Correction", "injectorLagTable", state)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Injector small pulse offset")
                _ts_dropdown("Apply", "injectorSmallPulseApply", state)
        with gr.Column(scale=1):
            gr.Plot(label="Gauges", elem_classes="ts-bg-dark")

def _render_thermistor(sensor_type: str, state: dict):
    title = sensor_type.replace("Sensor", "").upper() + " Sensor Calibration"
    _ts_header(title)
    
    # Determine the actual parameter prefixes based on sensor_type
    prefix = sensor_type.replace("Sensor", "").lower()
    if prefix == "iat": sensor_prefix = "iat"
    elif prefix == "clt": sensor_prefix = "clt"
    elif prefix == "cdt": sensor_prefix = "cdt" # Added for CDT sensor
    else: sensor_prefix = prefix
    
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Bias Resistor Settings")
                _ts_number("Bias Resistor(Ohms)", f"{sensor_prefix}BiasResistor", state)
            
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Thermistor Calibration (Steinhart-Hart)")
                _ts_number("Low Temp(C)", f"{sensor_prefix}TempLow", state)
                _ts_number("Low Resistance(Ohms)", f"{sensor_prefix}ResLow", state)
                gr.HTML("<hr style='margin:10px 0; border-color:#444;'/>")
                _ts_number("Mid Temp(C)", f"{sensor_prefix}TempMid", state)
                _ts_number("Mid Resistance(Ohms)", f"{sensor_prefix}ResMid", state)
                gr.HTML("<hr style='margin:10px 0; border-color:#444;'/>")
                _ts_number("High Temp(C)", f"{sensor_prefix}TempHigh", state)
                _ts_number("High Resistance(Ohms)", f"{sensor_prefix}ResHigh", state)
            
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Common Presets")
                with gr.Row():
                    gr.Button("Standard Bosch", variant="secondary")
                    gr.Button("GM Generic", variant="secondary")
                    gr.Button("Toyota/Denso", variant="secondary")
                
        with gr.Column(scale=1):
            gr.Plot(label="Transfer Curve", elem_classes="ts-bg-dark")
            gr.Plot(label="Current Value", elem_classes="ts-bg-dark")

def _render_generic_scalar(node_name: str, state: dict):
    _ts_header(f"Editing: {node_name}")
    # Search for a parameter that matches the node name
    p = _get_param(state, node_name)
    if not p:
        # Try to find common rusEFI names if the tree node name is different
        p = _get_param(state, node_name.replace(" ", ""))
    
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Scalar Value")
                if p:
                   if p.get("is_table") or p.get("is_array"):
                       _ts_table(p.get("name"), p.get("name"), state)
                   else:
                       _ts_number(p.get("name", "Value"), p.get("name"), state)
                else:
                    gr.Markdown(f"No parameter found for `{node_name}`")
        with gr.Column(scale=1):
            gr.Plot(label="Gauges", elem_classes="ts-bg-dark")
```
