
def _render_core_injection():
    _ts_header("Settings (Core Injection)")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Injection")
        _ts_dropdown("Injection", ["enabled", "disabled"], "enabled")
        _ts_dropdown("Mode", ["Sequential", "Batch", "Simultaneous"], "Sequential")
        _ts_label("Batch injection with individual wiring", is_blue=True)
        _ts_dropdown("Alpha-N uses IAT density correction", ["no", "yes"], "no", ghosted=True)
        _ts_dropdown("Override VE table load axis", ["None", "MAP", "TPS"], "None")
        _ts_dropdown("Override AFR table load axis", ["None", "MAP", "TPS"], "None")
        _ts_dropdown("Injection timing control mode", ["End of injection", "Start of injection"], "End of injection")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Injector Settings")
        _ts_number("Injector flow", 248.00)
        _ts_dropdown("Injector flow units", ["cc/min", "lb/hr", "g/s"], "cc/min")
        _ts_dropdown("Fuel rail pressure sensor", ["NONE"], "NONE", ghosted=True)
        _ts_dropdown("Injector flow compensation mode", ["Fixed rail pressure", "Differential"], "Fixed rail pressure")
        _ts_number("Injector reference pressure(kPa)", 294)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Fuel characteristics")
        _ts_number("Stoichiometric ratio(:1)", 14.7)
        _ts_number("E100 stoichiometric ratio(:1)", 9.0, ghosted=True)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Experimental settings, do not touch")
        _ts_label("Experimental, do not enable", is_red=True)
        _ts_dropdown("Use absolute fuel pressure for dead time calculation", ["no"], "no")

def _render_max_knock_retard():
    _ts_header("Max knock retard")
    gr.HTML("<div>Table editor placeholder 4x10</div>")

def _render_software_knock():
    _ts_header("Software Knock")
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Sense")
                _ts_dropdown("Knock sensing", ["enabled", "disabled"], "enabled")
                _ts_number("Cylinder Bore(mm)", 87.50)
                _ts_number("Estimated Knock Frequency(Hz)", 0)
                _ts_dropdown("Detection mode", ["second harmonic", "first harmonic"], "second harmonic")
                _ts_number("Detection Window Start(angle)", 20.00)
                _ts_number("Sampling Duration(Deg)", 45)
                _ts_dropdown("Enable Knock Spectrogram", ["no", "yes"], "no")
                _ts_dropdown("Enable Knock Spectrogram Filter", ["no", "yes"], "no", ghosted=True)
                _ts_number("Knock Spectrum Sensitivity(sense)", 0, ghosted=True)
                _ts_label("Select the nearest sensor for each cylinder")
                for i in range(1, 13):
                    _ts_dropdown(f"Cylinder {i}", ["Channel 1", "Channel 2"], "Channel 1", ghosted=(i>4))
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Response")
                _ts_number("Retard Aggression(%)", 20.0)
                _ts_number("Retard Reapply Rate(deg/s)", 3.0)
                _ts_number("Fuel Trim Aggression(%)", 0.0)
                _ts_number("Fuel Trim Reapply Rate(1%/s)", 0.0)
                _ts_number("Fuel Trim(%)", 0.0)
                _ts_number("Suppress Min Tps(%)", 10.0)
        with gr.Column(scale=1):
            gr.Plot(label="Threshold dB vs RPM", elem_classes="ts-bg-dark")
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

def _render_multispark():
    _ts_header("Multispark")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Multispark")
        _ts_label("WARNING! These settings have the potential to overheat ignition components", is_blue=True)
        _ts_label("and cause other nasty misbehavior. Use with care, at your own risk!", is_blue=True)
        _ts_label("Not recommended for use on distributor or wasted spark ignition systems.", is_blue=True)
        _ts_dropdown("Enable multiple sparks", ["no", "yes"], "no")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Configuration")
        _ts_number("Maximum engine speed(rpm)", 0, ghosted=True)
        _ts_number("Fire sparks for this angle duration(deg)", 0, ghosted=True)
        _ts_number("Maximum extra spark count", 0, ghosted=True)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Delay & Dwell")
        _ts_number("Spark duration(ms)", 0, ghosted=True)
        _ts_number("Subsequent spark dwell(ms)", 0, ghosted=True)

def _render_ignition_trim_1():
    _ts_header("Ignition trim cyl 1")
    gr.HTML("<div>Table editor placeholder 4x4</div>")

def _render_ignition_adder_1():
    _ts_header("Ignition adder 1 config")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Ignition adder 1 config")
        _ts_label("The bias table controls how much...", is_blue=True)
        _ts_label("is mixed in to...", is_blue=True)
        _ts_label("+10 in the table...", is_blue=True)
        _ts_label("The X axis...", is_blue=True)
        _ts_label("parameter below.", is_blue=True)
        _ts_dropdown("Blend parameter", ["Load", "TPS", "RPM"], "Load")
        _ts_dropdown("Y axis override", ["None"], "None", ghosted=True)
    gr.Plot(label="% bias vs param", elem_classes="ts-bg-dark")

def _render_ignition_hardware():
    _ts_header("Ignition hardware")
    with gr.Row():
        with gr.Column(scale=1):
            _ts_dropdown("Spark", ["enabled", "disabled"], "enabled")
            _ts_dropdown("Mode", ["Single Coil", "Sequential", "Wasted Spark"], "Single Coil")
            _ts_number("Spark hardware latency correction(uS)", 0)
            _ts_dropdown("Individually wired Wasted Spark", ["no", "yes"], "no", ghosted=True)
            _ts_dropdown("Override ignition table load axis", ["None"], "None")
            _ts_label("Use fixed timing while validating with a timing gun", is_blue=True)
            _ts_dropdown("Timing Mode", ["dynamic", "fixed"], "dynamic")
            _ts_number("Fixed Timing(deg)", 0.00, ghosted=True)
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Ignition Outputs")
                _ts_label("wire each output to the corresponding cylinder number", is_blue=True)
                _ts_label("rusEFI handles firing order", is_blue=True)
                _ts_label("Output Mode is dangerous and can burn out your coils...")
                _ts_dropdown("Ignition Output Mode", ["default"], "default")
                for i in range(1, 13):
                    _ts_dropdown(f"Ignition Output {i}", ["active pin", "NONE"], "active pin" if i==1 else "NONE", ghosted=(i>1))

def _render_dwell():
    _ts_header("Dwell")
    gr.Plot(label="Dwell time base", elem_classes="ts-bg-dark")
    gr.HTML("<div>Table editor placeholder 2x8</div>")
    gr.Plot(label="Battery Volts (volts)", elem_classes="ts-bg-dark")

def _render_iat_retard():
    _ts_header("Ignition Intake Air Temp correction")
    gr.HTML("<div>Table editor placeholder 8x8</div>")

def _render_clt_retard():
    _ts_header("Warmup timing correction")
    gr.HTML("<div>Table editor placeholder 8x8</div>")

def _render_ignition_advance():
    _ts_header("Ignition advance")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Load override")
        _ts_dropdown("Override ignition table load axis", ["None"], "None")
    gr.HTML("<div>Table editor placeholder 16x16</div>")
    gr.Markdown("Override the Y axis (load) value used...", elem_classes="muted")

def _render_cranking_tps():
    _ts_header("Cranking TPS Multiplier")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="Multiplier Ratio vs TPS (%)", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

def _render_cranking_clt():
    _ts_header("Cranking Coolant Temperature Multiplier")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="Multiplier vs Coolant (C)", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

def _render_cranking_cycle_base_fuel():
    _ts_header("Cranking Cycle Base Fuel")
    gr.HTML("<div>Table editor placeholder 8x8</div>")

def _render_priming_pulse():
    _ts_header("Priming fuel pulse")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Priming fuel pulse")
        _ts_number("Priming delay(sec)", 0.50)
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="Prime Pulse mg vs Coolant (C)", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

# Patch router to include new renders
new_router = """    if selected_node == "vehicleInfo":
        _render_vehicle_info()
    elif selected_node == "hardLimits":
        _render_limits_fallbacks()
    elif selected_node == "LowOilPressure":
        _render_low_oil_pressure()
    elif selected_node == "HighOilPressure":
        _render_high_oil_pressure()
    elif selected_node == "triggerHardware":
        _render_trigger()
    elif selected_node == "triggerAdvanced":
        _render_advanced_trigger()
    elif selected_node == "triggerGapOverride":
        _render_trigger_gap_override()
    elif selected_node == "batteryAlternator":
        _render_battery_alternator()
    elif selected_node == "ignitionKey":
        _render_ignition_key()
    elif selected_node == "statusLeds":
        _render_status_leds()
    elif selected_node == "Outputs":
        _render_outputs()
    elif selected_node == "cylinderBanks":
        _render_cylinder_banks()
    elif selected_node == "veTable1":
        _render_ve_table_3d()
    elif selected_node == "veTable2D":
        _render_ve_table_2d()
    elif selected_node == "injectorDeadTime":
        _render_injector_dead_time()
    elif selected_node == "coreInjection":
        _render_core_injection()
    elif selected_node == "maxKnockRetard":
        _render_max_knock_retard()
    elif selected_node == "softwareKnock":
        _render_software_knock()
    elif selected_node == "multispark":
        _render_multispark()
    elif selected_node == "ignitionTrim1":
        _render_ignition_trim_1()
    elif selected_node == "ignitionAdder1":
        _render_ignition_adder_1()
    elif selected_node == "ignitionHardware":
        _render_ignition_hardware()
    elif selected_node == "dwell":
        _render_dwell()
    elif selected_node == "iatRetard":
        _render_iat_retard()
    elif selected_node == "cltRetard":
        _render_clt_retard()
    elif selected_node == "ignitionAdvance":
        _render_ignition_advance()
    elif selected_node == "crankingTps":
        _render_cranking_tps()
    elif selected_node == "crankingClt":
        _render_cranking_clt()
    elif selected_node == "crankingCycleBaseFuel":
        _render_cranking_cycle_base_fuel()
    elif selected_node == "primingPulse":
        _render_priming_pulse()
    else:"""

import re
with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/components/dialog_renderer.py", "r") as f:
    code = f.read()

code = re.sub(r'    if selected_node == "vehicleInfo":.*?    else:', new_router, code, flags=re.DOTALL)
code += "\n" + additional_renders

with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/components/dialog_renderer.py", "w") as f:
    f.write(code)
