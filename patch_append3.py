
def _render_flex_sensor():
    _ts_header("Flex Sensor")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Flex Sensor")
                _ts_label("https://wiki.rusefi.com/Flex-Fuel", is_red=True)
                _ts_dropdown("Flex fuel sensor", ["NONE"], "NONE")
                _ts_text("Flex Signal", "Normal", ghosted=True)
        with gr.Column(scale=1):
            gr.Plot(label="Flex Ethanol %", elem_classes="ts-bg-dark")
            gr.Plot(label="Fuel Temperature", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw Flex", elem_classes="ts-bg-dark")

def _render_oil_temp_sensor():
    _ts_header("Oil Temp Sensor Settings")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Oil Temp Sensor Settings")
        _ts_dropdown("Input channel", ["NONE"], "NONE")
        _ts_number("Pullup resistor(Ohm)", 0.0, ghosted=True)
        _ts_number("Lowest temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ LT(Ohm)", 0.0, ghosted=True)
        _ts_number("Middle temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ MT(Ohm)", 0.0, ghosted=True)
        _ts_number("Highest temperature(*C)", 0.0, ghosted=True)
        _ts_number("Resistance @ HT(Ohm)", 0.0, ghosted=True)

def _render_oil_pressure_sensor():
    _ts_header("Settings (Oil Pressure Sensor)")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Oil Pressure Sensor")
                _ts_dropdown("Oil Pressure input", ["NONE"], "NONE")
                _ts_number("low voltage(volts)", 0.50, ghosted=True)
                _ts_number("low pressure", 0.00, ghosted=True)
                _ts_number("high voltage(volts)", 4.50, ghosted=True)
                _ts_number("high pressure", 689.48, ghosted=True)
        with gr.Column(scale=1):
            gr.Plot(label="Oil Pressure", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw Oil Pressure", elem_classes="ts-bg-dark")

def _render_wideband_tools():
    _ts_header("rusEFI Wideband Tools")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("rusEFI Wideband Tools")
        _ts_dropdown("Wideband CAN bus", ["CAN1"], "CAN1")
        _ts_dropdown("Target device HW ID", ["Idx 1"], "Idx 1")
        gr.Button("Ping/Get FW version")
        _ts_dropdown("Required CAN ID", ["ID1 0x190/191"], "ID1 0x190/191")
        gr.Button("Set Index")
        _ts_dropdown("Sensor type", ["Bosch LSU4.9"], "Bosch LSU4.9")
        gr.Button("Set sensor type")
        gr.Button("Update to 2026-01 Firmware")
        gr.Button("Flash FW from SD card")
        gr.Button("Restart all WBO")
        _ts_label("FW version and build date:", is_red=True)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Legacy 2023 (stock) firmware")
        _ts_label("Please connect exactly one wideband controller before pressing this button!", is_red=True)
        _ts_label("Please do not use if you already have 2025+ FW in your WBO", is_red=True)
        gr.Button("Update 2023 Firmware to 2026")
    _ts_label("Idle", is_blue=True) # closest substitute for Green Banner
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("rusEFI Wideband 1 auto remap")
        _ts_dropdown("Auto remap on start", ["no", "yes"], "no")
        _ts_dropdown("rusEFI WBO hardware index", ["NONE"], "NONE", ghosted=True)
        _ts_dropdown("rusEFI WBO CAN ID", ["NONE"], "NONE", ghosted=True)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("rusEFI Wideband 2 auto remap")
        _ts_dropdown("Auto remap on start", ["no", "yes"], "no")
        _ts_dropdown("rusEFI WBO hardware index", ["NONE"], "NONE", ghosted=True)
        _ts_dropdown("rusEFI WBO CAN ID", ["NONE"], "NONE", ghosted=True)

def _render_analog_o2():
    _ts_header("Analog O2 sensor")
    _ts_label("Disable CAN O2 sensor(s) to enable this settings")
    _ts_number("Smoothing Factor", 1.000)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("O2 sensor")
        _ts_dropdown("O2 Type", ["Custom"], "Custom")
        _ts_dropdown("Type", ["14Point7"], "14Point7", ghosted=True)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("O2 Sensor 1 I/O")
        _ts_dropdown("Input channel", ["NONE"], "NONE", ghosted=True)
        _ts_dropdown("Narrowband Heater output", ["NONE"], "NONE", ghosted=True)
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("O2 Sensor 2 I/O")
        _ts_dropdown("Input channel", ["NONE"], "NONE", ghosted=True)

def _render_can_o2():
    _ts_header("CAN O2 sensors")
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("CAN UEGO 1")
                _ts_dropdown("UEGO type", ["RusEFI"], "RusEFI")
                _ts_dropdown("RusEFI WBO ID", ["ID1 0x190/191"], "ID1 0x190/191")
                _ts_dropdown("AEM ID", ["NONE"], "NONE", ghosted=True)
                gr.Plot(label="Gauges", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("CAN O2 sensors")
                _ts_label("Support for AEM or RusEFI CAN UEGO")
                _ts_dropdown("Enable CAN Wideband", ["no", "yes"], "yes")
                _ts_dropdown("Wideband CAN bus", ["CAN1"], "CAN1")
                _ts_number("Smoothing Factor", 1.000)
                _ts_label("Warning about force heating outside workshop.", is_red=True)
                _ts_dropdown("Force O2 sensor heating", ["no", "yes"], "no")
                gr.Button("Restart all WBO")
                gr.Button("Update 2023 Firmware from file")
        with gr.Column(scale=1):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("CAN UEGO 2")
                _ts_dropdown("UEGO type", ["RusEFI"], "RusEFI")
                _ts_dropdown("RusEFI WBO ID", ["ID2 0x192/193"], "ID2 0x192/193")
                _ts_dropdown("AEM ID", ["NONE"], "NONE", ghosted=True)
                gr.Plot(label="Gauges", elem_classes="ts-bg-dark")

def _render_maf_sensor():
    _ts_header("MAF sensor")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("MAF sensor")
        _ts_label("https://wiki.rusefi.com/MAF", is_red=True)
        _ts_dropdown("MAF ADC input", ["NONE"], "NONE")
        _ts_dropdown("MAF 2 ADC input", ["NONE"], "NONE")
        _ts_number("MAF filter parameter", 1, precision=0)

def _render_baro_sensor():
    _ts_header("Baro sensor")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Baro sensor")
        with gr.Group(elem_classes="ts-fieldset"):
            _ts_header("Analog Sensor")
            _ts_dropdown("Baro input", ["NONE"], "NONE", ghosted=True)
            _ts_number("Low Value(kPa)", 0.0, ghosted=True)
            _ts_number("High Value(kPa)", 0.0, ghosted=True)
            _ts_dropdown("Type", ["Custom"], "Custom", ghosted=True)
        with gr.Group(elem_classes="ts-fieldset"):
            _ts_header("Digital Sensor")
            _ts_dropdown("LPS2x Baro SCL", ["PB10"], "PB10")
            _ts_dropdown("LPS2x Baro SDA", ["PB11"], "PB11")

def _render_map_sampling():
    _ts_header("MAP sampling")
    _ts_dropdown("Window averaging", ["enabled", "disabled"], "enabled")
    _ts_number("mapExpAverageAlpha", 1.000)
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="Angle deg vs RPM", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Plot(label="Window deg vs RPM", elem_classes="ts-bg-dark")
        with gr.Column(scale=1):
            gr.Plot(label="Gauge", elem_classes="ts-bg-dark")
            gr.HTML("<div>Table editor placeholder 2x8</div>")

def _render_map_sensor():
    _ts_header("MAP sensor")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("MAP common settings")
                _ts_number("Low value threshold(kPa)", 5.00)
                _ts_number("High value threshold(kPa)", 250.00)
                _ts_dropdown("Measure Map Only In One Cylinder", ["no", "yes"], "no")
                _ts_number("Cylinder count to sample MAP(count)", 1, precision=0)
                _ts_number("MAP sensor ExpAverage dampening", 1.000)
                _ts_label("BAD Map Input", is_red=True)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("MAP sensor")
                _ts_dropdown("MAP input", ["D9 MAP"], "D9 MAP")
                _ts_dropdown("MAP type", ["DENSO183"], "DENSO183")
                _ts_number("Low/High points & voltages", 0.00, ghosted=True)
        with gr.Column(scale=1):
            gr.Plot(label="MAP (0-300)", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw MAP (0-5 V)", elem_classes="ts-bg-dark")

def _render_tps():
    _ts_header("TPS")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Throttle Body #1 Sensor(s)")
                _ts_dropdown("Primary sensor input", ["D13 TPS1"], "D13 TPS1")
                _ts_number("Primary closed(V)", 0.62)
                _ts_number("Primary open(V)", 4.60)
                _ts_dropdown("Secondary sensor input", ["NONE"], "NONE")
                gr.Button("Auto Calibrate ETB 1", interactive=False)
                gr.Button("Grab Closed Throttle voltage")
                gr.Button("Grab Fully Opened Throttle voltage")
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("Throttle Body #2 Sensor(s)")
                _ts_dropdown("Primary sensor", ["NONE"], "NONE")
                gr.Button("Auto Calibrate ETB 2", interactive=False)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("SENT TPS")
                gr.Markdown("*(Settings ghosted)*", elem_classes="muted")
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("TPS/PPS Limits")
                _ts_number("TPS/PPS min valid value(%)", -10)
                _ts_number("TPS/PPS max valid value(%)", 110)
                _ts_number("TPS/PPS Error Detection Threshold(%)", 5.0)
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("ETB Position Sensors special cases")
                gr.Markdown("*(Settings ghosted)*", elem_classes="muted")
        with gr.Column(scale=1):
            gr.Plot(label="Raw TPS 1 Primary", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw TPS 1 Secondary", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw TPS 2 Primary", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw TPS 2 Secondary", elem_classes="ts-bg-dark")

def _render_iat_sensor():
    _ts_header("IAT Sensor")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("IAT Sensor")
                _ts_dropdown("Input channel", ["D15 IAT"], "D15 IAT")
                _ts_dropdown("Common IAT Sensors", ["Custom"], "Custom")
                _ts_label("Information text.", is_blue=True)
                _ts_dropdown("Linear characteristic", ["no", "yes"], "no")
        with gr.Column(scale=1):
            gr.Plot(label="Intake air temp", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw IAT", elem_classes="ts-bg-dark")

def _render_clt_sensor():
    _ts_header("CLT Sensor")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("CLT sensor")
                _ts_dropdown("Input channel", ["D16 CLT Coolant"], "D16 CLT Coolant")
                _ts_dropdown("Common CLT Sensors", ["Custom"], "Custom")
                _ts_label("Information text.", is_blue=True)
                _ts_dropdown("Linear characteristic", ["no", "yes"], "no")
        with gr.Column(scale=1):
            gr.Plot(label="Coolant temp", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw CLT", elem_classes="ts-bg-dark")

def _render_analog_input_settings():
    _ts_header("Analog Input Settings")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Analog Input Settings")
        _ts_label("ECU reboot needed to apply these settings", is_red=True)
        _ts_dropdown("Grab baro value from MAP", ["no", "yes"], "no")

def _render_ac_pressure_sensor():
    _ts_header("Settings (A/C Pressure Sensor)")
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group(elem_classes="ts-fieldset"):
                _ts_header("A/C Pressure Sensor")
                _ts_dropdown("Input", ["NONE"], "NONE")
                _ts_number("Low voltage(volts)", 0.00, ghosted=True)
                _ts_number("Low value", 0.00, ghosted=True)
                _ts_number("High voltage(volts)", 5.00, ghosted=True)
                _ts_number("High value", 100.00, ghosted=True)
        with gr.Column(scale=1):
            gr.Plot(label="A/C pressure", elem_classes="ts-bg-dark")
            gr.Plot(label="Raw A/C Pressure", elem_classes="ts-bg-dark")

def _render_ambient_temp_sensor():
    _ts_header("Ambient Temp Sensor Settings")
    with gr.Group(elem_classes="ts-fieldset"):
        _ts_header("Ambient Temp Sensor Settings")
        _ts_label("Put this sensor before any turbocharger/supercharger", is_red=True)
        _ts_label("near the air filter.", is_red=True)
        _ts_dropdown("Input channel", ["NONE"], "NONE")
        _ts_number("Pullup resistor(Ohm)", 0.0, ghosted=True)
        _ts_number("Lowest temperature(*C)", 0.0, ghosted=True)


# Patch router to include new renders
new_router_3 = """    elif selected_node == "flexSensor":
        _render_flex_sensor()
    elif selected_node == "oilTempSensor":
        _render_oil_temp_sensor()
    elif selected_node == "oilPressureSensor":
        _render_oil_pressure_sensor()
    elif selected_node == "widebandTools":
        _render_wideband_tools()
    elif selected_node == "analogO2":
        _render_analog_o2()
    elif selected_node == "canO2":
        _render_can_o2()
    elif selected_node == "mafSensor":
        _render_maf_sensor()
    elif selected_node == "baroSensor":
        _render_baro_sensor()
    elif selected_node == "mapSampling":
        _render_map_sampling()
    elif selected_node == "mapSensor":
        _render_map_sensor()
    elif selected_node == "tps":
        _render_tps()
    elif selected_node == "iatSensor":
        _render_iat_sensor()
    elif selected_node == "cltSensor":
        _render_clt_sensor()
    elif selected_node == "analogInputSettings":
        _render_analog_input_settings()
    elif selected_node == "acPressureSensor":
        _render_ac_pressure_sensor()
    elif selected_node == "ambientTempSensor":
        _render_ambient_temp_sensor()
    else:"""

import re
with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/components/dialog_renderer.py", "r") as f:
    code = f.read()

code = re.sub(r'    else:', new_router_3, code, flags=re.DOTALL)
code += "\n" + additional_renders

with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/components/dialog_renderer.py", "w") as f:
    f.write(code)
