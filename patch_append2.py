
def _render_ase_enrichment():
    _ts_header("After start enrichment")
    gr.HTML("<div>Table editor placeholder 2x16</div>")

def _render_cranking_air_clt():
    _ts_header("Cranking Air Amount vs CLT")
    _ts_number("ETB idle maximum angle(%)", 15)
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="Percent vs Coolant (C)", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

def _render_cranking_settings():
    _ts_header("Cranking Settings")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Cranking Settings")
        _ts_number("Cranking RPM limit(RPM)", 550, precision=0)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Fuel")
        _ts_dropdown("Injection mode", ["Simultaneous", "Sequential"], "Simultaneous")
        _ts_dropdown("Fuel Source For Cranking", ["Fixed", "Map"], "Fixed")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Ignition")
        _ts_dropdown("Timing Advance mode", ["Fixed (auto taper)", "Dynamic"], "Fixed (auto taper)")
        _ts_number("Fixed cranking advance(deg)", 6, precision=0)
        _ts_number("Fixed Cranking Dwell(ms)", 6.0)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Advanced")
        _ts_dropdown("Flood clear", ["enabled", "disabled"], "enabled")
        _ts_dropdown("Faster engine spin-up", ["enabled", "disabled"], "enabled")
        _ts_dropdown("Use Advance Corrections for cranking", ["no", "yes"], "no")
        _ts_dropdown("Separate Flex Fuel cranking table", ["disabled"], "disabled", ghosted=True)

def _render_idle_ase_taper():
    _ts_header("Idle After Start (Crank-to-Run) Taper vs CLT")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="cycles vs Coolant (C)", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

def _render_open_loop_idle_clt():
    _ts_header("Open Loop Idle position CLT vs Target Rpm")
    gr.HTML("<div>Table editor placeholder 2x16</div>")

def _render_idle_settings():
    _ts_header("Idle settings")
    _ts_dropdown("Idle control mode", ["Open Loop", "Closed Loop"], "Open Loop")
    _ts_label("Solenoid idle control is disabled at zero RPM", is_red=True)
    _ts_label("https://wiki.rusefi.com/Idle-Control", is_red=True)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Idle Detection Thresholds")
        _ts_number("TPS threshold(%)", 5)
        _ts_number("RPM upper limit(RPM)", 300)
        _ts_number("RPM deadzone(RPM)", 50)
        _ts_number("Max vehicle speed(kmh)", 0)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Open Loop Idle")
        _ts_number("A/C adder", 0)
        _ts_number("Fan #1 adder", 0)
        _ts_number("Fan #2 adder", 0)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Closed Loop Idle")
        gr.Markdown("*(Settings ghosted)*", elem_classes="muted")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Extra Idle Features")
        _ts_dropdown("Separate idle ignition table", ["disabled", "enabled"], "disabled")
        _ts_dropdown("Separate idle VE table", ["disabled", "enabled"], "disabled")
        _ts_dropdown("Separate idle tables for cranking taper", ["disabled", "enabled"], "disabled")
        _ts_dropdown("Separate coasting idle table", ["disabled", "enabled"], "disabled")
        _ts_number("Dashpot coasting-to-idle Initial idle Adder(percent)", 2)
        _ts_number("Dashpot coasting-to-idle Hold time(seconds)", 0.0)
        _ts_number("Dashpot coasting-to-idle Decay time(seconds)", 0.0)

def _render_idle_target_rpm():
    _ts_header("Idle Target RPM")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="RPM vs Coolant (C)", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

def _render_idle_hardware():
    _ts_header("Idle hardware")
    _ts_label("ECU reboot needed to apply these settings", is_red=True)
    _ts_dropdown("Use Stepper", ["no", "yes"], "no")
    _ts_number("Electronic throttle idle range(%)", 15)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Idle Valve Hardware")
        with gr.Group(elem_classes="ts-fieldset"):
            _ts_header("Solenoid")
            _ts_dropdown("Idle Solenoid Primary output", ["NONE"], "NONE")
            _ts_dropdown("Double Solenoid Mode", ["no", "yes"], "no")
            _ts_dropdown("Idle Solenoid Secondary output", ["NONE"], "NONE")
            _ts_dropdown("Idle Solenoid output(s) Mode", ["default"], "default")
            _ts_number("Idle Solenoid Frequency(Hz)", 300)
        with gr.Group(elem_classes="ts-fieldset"):
            _ts_header("Stepper")
            gr.Markdown("*(Settings ghosted)*", elem_classes="muted")

def _render_other_sensors():
    _ts_header("Other Sensor Inputs")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Other Sensor Inputs")
        _ts_dropdown("Clutch Down", ["NONE"], "NONE")
        _ts_dropdown("Clutch Down mode", ["PULLUP", "PULLDOWN"], "PULLUP")
        _ts_dropdown("Clutch Up", ["NONE"], "NONE")
        _ts_dropdown("Clutch Up mode", ["PULLUP", "PULLDOWN"], "PULLUP")
        _ts_dropdown("Brake Pedal", ["NONE"], "NONE")
        _ts_dropdown("Brake Pedal Mode", ["PULLUP", "PULLDOWN"], "PULLUP")
        _ts_dropdown("Turbo Speed Sensor", ["NONE"], "NONE")
        _ts_number("Turbo Speed Multiplier(mult)", 1.000, ghosted=True)
        _ts_dropdown("Throttle inlet pressure sensor", ["NONE"], "NONE")
        _ts_dropdown("Compressor discharge pressure sensor", ["NONE"], "NONE")

def _render_vr1_threshold():
    _ts_header("Settings - VR 1 Threshold")
    gr.Plot(label="Voltage Volts vs RPM (rpm)", elem_classes="ts-bg-dark")

def _render_speed_sensor():
    _ts_header("Speed sensor")
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Speed sensor")
                _ts_dropdown("Input", ["C7 HALL3"], "C7 HALL3")
                _ts_number("Filter parameter", 3, precision=0)
                _ts_number("Wheel revolutions per kilometer(revs/km)", 1000.0)
                _ts_number("Speed sensor gear ratio", 3.730, precision=3)
                _ts_number("Speed sensor tooth count", 21, precision=0)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("CAN Vehicle Speed")
                _ts_dropdown("Enable CAN VSS", ["no", "yes"], "no")
                _ts_dropdown("CAN VSS type", ["BMW_e46"], "BMW_e46", ghosted=True)
                _ts_number("CAN VSS scaling(ratio)", 1.0000, precision=4)
        with gr.Column(scale=1):
            gr.Plot(label="Gauge Vehicle Speed", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Gear Detection")
                _ts_number("Wheel revolutions per kilometer(revs/km)", 1000.0)
                _ts_number("Final drive ratio", 1.00)
                _ts_number("Forward gear count", 0, precision=0)
                for i in range(1, 9):
                    _ts_number(f"{i}st gear(ratio)" if i==1 else f"{i}th gear(ratio)", 0.00, ghosted=True)

def _render_comp_discharge_temp():
    _ts_header("Compressor Discharge Temp Settings")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Compressor Discharge Temp Settings")
        _ts_label("Put this sensor after the turbocharger/supercharger", is_red=True)
        _ts_label("but before the intercooler.", is_red=True)
        _ts_dropdown("Input channel", ["NONE"], "NONE")
        _ts_number("Pullup resistor(Ohm)", 0.0, ghosted=True)
        _ts_number("Lowest temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ LT(Ohm)", 0.0, ghosted=True)
        _ts_number("Middle temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ MT(Ohm)", 0.0, ghosted=True)
        _ts_number("Highest temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ HT(Ohm)", 0.0, ghosted=True)

def _render_egt_inputs():
    _ts_header("EGT inputs")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("CAN EGT sensors")
        _ts_label("CAN support EGT1 to EGT6 inputs")
        _ts_dropdown("CAN EGT (AEM X series of RusEFI)", ["no", "yes"], "no")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("SPI EGT sensors")
        _ts_label("If both CAN and SPI EGT sensors are used...")
        _ts_dropdown("MAX31855/MAX31856 SPI", ["SPI3", "NONE"], "SPI3")
        _ts_dropdown("CS for EGT1", ["PA15", "NONE"], "PA15")
        for i in range(2, 9):
            _ts_dropdown(f"CS for EGT{i}", ["NONE"], "NONE")

def _render_fuel_level_sensor():
    _ts_header("Fuel Level Sensor")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Fuel Level Sensor")
                _ts_dropdown("Input channel", ["NONE"], "NONE")
                _ts_number("Low threshold(v)", 0.25, ghosted=True)
                _ts_number("High threshold(v)", 4.50, ghosted=True)
                _ts_number("Filter Alpha", 0.0010, precision=4)
                _ts_number("Update period(seconds)", 0.100, precision=3)
            gr.Plot(label="% vs Voltage (volt)", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Raw Fuel Level (0-5 V)", elem_classes="ts-bg-dark")
            gr.Plot(label="Fuel level (0-100 %)", elem_classes="ts-bg-dark")

def _render_fuel_temp_sensor():
    _ts_header("Fuel Temp Sensor Settings")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Fuel Temp Sensor Settings")
        _ts_dropdown("Input channel", ["NONE"], "NONE")
        _ts_number("Pullup resistor(Ohm)", 0.0, ghosted=True)
        _ts_number("Lowest temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ LT(Ohm)", 0.0, ghosted=True)
        _ts_number("Middle temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ MT(Ohm)", 0.0, ghosted=True)
        _ts_number("Highest temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ HT(Ohm)", 0.0, ghosted=True)

def _render_fuel_pressure_sensor():
    _ts_header("Settings (Fuel Pressure Sensor)")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Fuel Low Pressure Sensor")
                _ts_dropdown("Analog input", ["NONE"], "NONE")
                _ts_dropdown("sensor type", ["Absolute"], "Absolute", ghosted=True)
                with gr.Group(elem_classes="ts-fieldset"):
                    _ts_header("Sensor scaling")
                    _ts_number("low voltage(volts)", 0.00, ghosted=True)
                    _ts_number("low pressure", 0.00, ghosted=True)
                    _ts_number("high voltage(volts)", 5.00, ghosted=True)
                    _ts_number("high pressure", 100.00, ghosted=True)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Fuel High Pressure Sensor")
                _ts_dropdown("Sensor SENT type", ["None"], "None")
                _ts_dropdown("Sensor SENT input", ["None"], "None", ghosted=True)
                _ts_dropdown("Analog input", ["NONE"], "NONE")
                with gr.Group(elem_classes="ts-fieldset"):
                    _ts_header("Sensor scaling")
                    _ts_number("low voltage(volts)", 0.00, ghosted=True)
                    _ts_number("low pressure", 0.00, ghosted=True)
                    _ts_number("high voltage(volts)", 5.00, ghosted=True)
                    _ts_number("high pressure", 100.00, ghosted=True)
        with gr.Column(scale=1):
            gr.Plot(label="Fuel pressure (low)", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw fuel pressure (low)", elem_classes="ts-bg-dark")
            gr.Plot(label="Fuel pressure (high)", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw fuel pressure (high)", elem_classes="ts-bg-dark")

# Patch router to include new renders
new_router_2 = """    elif selected_node == "aseEnrichment":
        _render_ase_enrichment()
    elif selected_node == "crankingAirClt":
        _render_cranking_air_clt()
    elif selected_node == "crankingSettings":
        _render_cranking_settings()
    elif selected_node == "idleAseTaper":
        _render_idle_ase_taper()
    elif selected_node == "openLoopIdleClt":
        _render_open_loop_idle_clt()
    elif selected_node == "idleSettings":
        _render_idle_settings()
    elif selected_node == "idleTargetRpm":
        _render_idle_target_rpm()
    elif selected_node == "idleHardware":
        _render_idle_hardware()
    elif selected_node == "otherSensors":
        _render_other_sensors()
    elif selected_node == "vr1Threshold":
        _render_vr1_threshold()
    elif selected_node == "speedSensor":
        _render_speed_sensor()
    elif selected_node == "compDischargeTemp":
        _render_comp_discharge_temp()
    elif selected_node == "egtInputs":
        _render_egt_inputs()
    elif selected_node == "fuelLevelSensor":
        _render_fuel_level_sensor()
    elif selected_node == "fuelTempSensor":
        _render_fuel_temp_sensor()
    elif selected_node == "fuelPressureSensor":
        _render_fuel_pressure_sensor()
    else:"""

import re
with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/components/dialog_renderer.py", "r") as f:
    code = f.read()

code = re.sub(r'    else:', new_router_2, code, flags=re.DOTALL)
code += "\n" + additional_renders

with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/components/dialog_renderer.py", "w") as f:
    f.write(code)
