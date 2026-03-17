from machine import I2C, Pin
from machine import UART
import time
import math

# ============================================================
# UART SETUP
# ============================================================
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

# ============================================================
# I2C SETUP
# ============================================================
I2C_FREQ = 25_000
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=I2C_FREQ)

# ============================================================
# ADS1115 CONFIG
# ============================================================
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# MUX bits for AIN0-3 (single-ended)
MUX = [
    0x4000,  # AIN0
    0x5000,  # AIN1
    0x6000,  # AIN2
    0x7000   # AIN3
]

# PGA ±6.144V
PGA_6_144 = 0x0000
MODE_SINGLE = 0x0100
DR_128SPS = 0x0080
COMP_DISABLE = 0x0003

# ±0.256V range
PGA_0_256 = 0x0A00

BASE_CONFIG = PGA_6_144 | MODE_SINGLE | DR_128SPS | COMP_DISABLE
ADC_LSB = 6.144 / 32768  # volts per bit

# ============================================================
# ADC ADDRESSES
# ============================================================
ADC_48 = 0x48
ADC_49 = 0x49
ADC_4A = 0x4A

# ============================================================
# DAC ADDRESS (MCP4725)
# ============================================================
DAC_60 = 0x60   # Change if A0 tied differently
DAC_VREF = 5.0  # MCP4725 powered from +5V_VR per schematic
DAC_DIVIDER_GAIN = 5.1 / (100.0 + 5.1)
DEBUG_DAC = True
DAC_WRITE_RETRIES = 99999999999999
DAC_CAL_POINTS = (
    (0.53, 0.0),
    (1.44, 1.0),
    (2.30, 2.0),
    (3.24, 3.0),
    (4.15, 4.0),
    (5.00, 5.0),
)

REQUIRED_I2C_DEVICES = {
    ADC_48: "ADS1115 @ 0x48",
    ADC_49: "ADS1115 @ 0x49",
    ADC_4A: "ADS1115 @ 0x4A",
    DAC_60: "MCP4725 @ 0x60",
}

# ============================================================
# CHANNEL MAP (CONFIRMED)
# ============================================================

# --- 0x48 ---
CH_V_SENSE     = 0
CH_TEST_V1_DIV = 1
CH_DRIVER_V    = 2
CH_POWER_V     = 3

# --- 0x49 ---
CH_PYRANOMETER = 0
CH_I_SET_POT   = 1
CH_PANEL_TEMP  = 2
CH_5V_VR       = 3

# --- 0x4A ---
CH_BATT_TEMP   = 0
CH_SINK_TEMP   = 1
CH_AUX_I       = 2
CH_PRE_DRIVER  = 3

# ============================================================
# THERMISTOR CONSTANTS
# ============================================================
R_FIXED  = 4990.0

R0   = 12000
T0   = 298.15
BETA = 3950.0

# ============================================================
# HALL SENSOR CONSTANT
# ============================================================
HALL_V_PER_AMP = 0.150  # <-- replace with measured value if needed

# ============================================================
# SHUNT CONSTANT (20A / 75mV)
# ============================================================
SHUNT_RESISTANCE = 0.00375  # ohms

# ============================================================
# SHUNT CURRENT FUNCTION (20A / 75mV)
# ============================================================
def shunt_current(v_shunt):
    """
    Converts measured shunt voltage to current.
    Expects voltage already in volts.
    """
    return v_shunt / SHUNT_RESISTANCE

# ============================================================
# SAFE FORMAT FUNCTION
# ============================================================
def fmt(v, digits=3):
    return f"{v:.{digits}f}" if isinstance(v, (int, float)) else "ERR"


def reset_i2c():
    global i2c
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=I2C_FREQ)
    return i2c.scan()

# ============================================================
# ADS READ FUNCTION
# ============================================================
def read_ads(addr, channel):
    config = 0x8000 | MUX[channel] | BASE_CONFIG
    try:
        i2c.writeto_mem(addr, REG_CONFIG, config.to_bytes(2, "big"))
    except OSError as exc:
        raise RuntimeError(
            "I2C write failed for device 0x{:02X} channel {}: {}".format(addr, channel, exc)
        ) from exc
    time.sleep_ms(8)

    try:
        data = i2c.readfrom_mem(addr, REG_CONVERSION, 2)
    except OSError as exc:
        raise RuntimeError(
            "I2C read failed for device 0x{:02X} channel {}: {}".format(addr, channel, exc)
        ) from exc
    raw = int.from_bytes(data, "big")

    if raw & 0x8000:
        raw -= 65536

    return raw * ADC_LSB

# ============================================================
# MCP4725 WRITE FUNCTION
# ============================================================
def write_dac_voltage(voltage):
    """
    Writes a voltage (in volts) to MCP4725.
    Automatically clamps to DAC range.
    """
    clamped_voltage = min(max(voltage, 0.0), DAC_VREF)

    # Convert voltage to 12-bit value
    dac_value = int(round((clamped_voltage / DAC_VREF) * 4095))

    # MCP4725 fast-write format:
    # byte0 = [C2 C1 PD1 PD0 D11 D10 D9 D8], byte1 = [D7..D0]
    buffer = bytearray(2)
    buffer[0] = (dac_value >> 8) & 0x0F
    buffer[1] = dac_value & 0xFF

    last_error = None
    for attempt in range(1, DAC_WRITE_RETRIES + 1):
        try:
            i2c.writeto(DAC_60, buffer)
            return clamped_voltage, dac_value, True, attempt, None
        except OSError as exc:
            last_error = exc
            time.sleep_ms(10)
            try:
                found = reset_i2c()
                print(
                    "DAC WARN -> write attempt {} failed: {}. I2C scan after reset: {}".format(
                        attempt, exc, [hex(addr) for addr in found]
                    )
                )
            except OSError as scan_exc:
                print(
                    "DAC WARN -> write attempt {} failed: {}. I2C reset/scan failed: {}".format(
                        attempt, exc, scan_exc
                    )
                )
                time.sleep_ms(20)

    return clamped_voltage, dac_value, False, DAC_WRITE_RETRIES, last_error


def calibrated_dac_target(desired_voltage):
    """
    Convert the desired measured DAC voltage into a corrected DAC command
    using piecewise-linear interpolation of measured calibration points.
    """
    desired = min(max(desired_voltage, 0.0), DAC_VREF)

    if desired <= DAC_CAL_POINTS[0][0]:
        return DAC_CAL_POINTS[0][1]

    for index in range(1, len(DAC_CAL_POINTS)):
        measured_low, command_low = DAC_CAL_POINTS[index - 1]
        measured_high, command_high = DAC_CAL_POINTS[index]

        if desired <= measured_high:
            span = measured_high - measured_low
            if span <= 0:
                return command_high

            fraction = (desired - measured_low) / span
            return command_low + (fraction * (command_high - command_low))

    return DAC_CAL_POINTS[-1][1]


def scan_i2c_or_die():
    found = i2c.scan()
    print("I2C devices found:", [hex(addr) for addr in found])

    missing = [label for addr, label in REQUIRED_I2C_DEVICES.items() if addr not in found]
    if missing:
        raise RuntimeError("Missing I2C device(s): {}".format(", ".join(missing)))

# ============================================================
# THERMISTOR FUNCTION
# ============================================================
def thermistor_temp(v_adc, V_SUPPLY):
    if v_adc <= 0 or v_adc >= V_SUPPLY:
        return None

    r = R_FIXED * (V_SUPPLY - v_adc) / v_adc
    if r <= 0:
        return None

    ln = math.log(r / R0)
    temp_k = 1 / ((1/T0) + (ln / BETA))
    return temp_k - 273.15

# ============================================================
# HALL ZERO CALIBRATION
# ============================================================
def calibrate_aux():
    print("Calibrating Aux current zero (no load)...")
    time.sleep(2)

    total = 0
    samples = 50

    for _ in range(samples):
        total += read_ads(ADC_4A, CH_AUX_I)
        time.sleep_ms(5)

    zero = total / samples
    print("Zero offset:", zero)
    print("----------------------------------")
    return zero

# ============================================================
# STARTUP CALIBRATION
# ============================================================
UOUT_ZERO = 2.5 # calibrate_aux()

def calibrate_shunt_zero(addr):
    print("Calibrating shunt zero (no load)...")
    time.sleep(2)

    total = 0
    samples = 100

    for _ in range(samples):
        total += read_ads(addr, CH_V_SENSE)
        time.sleep_ms(5)

    zero = total / samples
    print("Shunt zero offset:", zero)
    print("----------------------------------")
    return zero

# ============================================================
# HIGH RESOLUTION SHUNT READ (20A / 75mV)
# ============================================================
def read_shunt_current(addr, channel):
    """
    Reads shunt voltage using ±0.256V PGA for high resolution.
    Does NOT affect other ADC channels.
    """

    # Local config using high gain
    config = 0x8000 | MUX[channel] | PGA_0_256 | MODE_SINGLE | DR_128SPS | COMP_DISABLE
    i2c.writeto_mem(addr, REG_CONFIG, config.to_bytes(2, "big"))
    time.sleep_ms(8)

    data = i2c.readfrom_mem(addr, REG_CONVERSION, 2)
    raw = int.from_bytes(data, "big")

    if raw & 0x8000:
        raw -= 65536

    # LSB for ±0.256V
    lsb = 0.256 / 32768.0
    v_shunt = raw * lsb

    # 20A / 75mV shunt
    return (v_shunt - SHUNT_ZERO) / 0.00375

# ============================================================
# MAIN LOOP
# ============================================================
scan_i2c_or_die()
SHUNT_ZERO = calibrate_shunt_zero(ADC_48)

print("Starting telemetry loop...\n")

while True:

    # -------- 0x48 --------
    V_Sense     = read_ads(ADC_48, CH_V_SENSE)
    Test_V1_Div = read_ads(ADC_48, CH_TEST_V1_DIV)
    Driver_V    = read_ads(ADC_48, CH_DRIVER_V)
    Power_V     = read_ads(ADC_48, CH_POWER_V)

    # -------- 0x49 --------
    Pyranometer = read_ads(ADC_49, CH_PYRANOMETER)
    I_SET_POT_V = read_ads(ADC_49, CH_I_SET_POT)
    # Pre-distort the DAC command so the measured output better matches the pot.
    DAC_Target_V = calibrated_dac_target(I_SET_POT_V)
    DAC_Command_V, DAC_Code, DAC_Write_OK, DAC_Write_Attempts, DAC_Write_Error = write_dac_voltage(DAC_Target_V)
    CURRENT_SET_EXPECTED_V = min(max(I_SET_POT_V, 0), DAC_VREF) * DAC_DIVIDER_GAIN
    Panel_T_V   = read_ads(ADC_49, CH_PANEL_TEMP)
    VR_5V       = read_ads(ADC_49, CH_5V_VR)

    # -------- 0x4A --------
    Batt_T_V    = read_ads(ADC_4A, CH_BATT_TEMP)
    Sink_T_V    = read_ads(ADC_4A, CH_SINK_TEMP)
    Aux_V       = read_ads(ADC_4A, CH_AUX_I)
    Pre_Driver  = read_ads(ADC_4A, CH_PRE_DRIVER)

    # -------- Conversions --------
    Panel_Temp = thermistor_temp(Panel_T_V, VR_5V)
    Batt_Temp  = thermistor_temp(Batt_T_V, VR_5V)
    Sink_Temp  = thermistor_temp(Sink_T_V, VR_5V)

    AuxI = -1* ((Aux_V - UOUT_ZERO) / HALL_V_PER_AMP) - 0.05
    I_SET_Percent = (I_SET_POT_V / VR_5V) * 100.0

    TestI = read_shunt_current(ADC_48, CH_V_SENSE)
    TestV = 11*Test_V1_Div

    # -------- Output --------
    output = (
        f"TestI:{fmt(TestI)}, "
        f"TV1:{fmt(Test_V1_Div)}, "
        f"DRV:{fmt(Driver_V)}, "
        f"PWR:{fmt(Power_V)}, "
        f"PYR:{fmt(Pyranometer)}, "
        f"POT%:{fmt(I_SET_Percent,1)}, "
        f"I_SET_POT:{fmt(I_SET_POT_V)}, "
        f"DACcmd:{fmt(DAC_Command_V)}, "
        f"DACcode:{DAC_Code}, "
        f"DACok:{DAC_Write_OK}, "
        f"DACtries:{DAC_Write_Attempts}, "
        f"CurrentSetExp:{fmt(CURRENT_SET_EXPECTED_V)}, "
        f"5VR:{fmt(VR_5V)}, "
        f"PanelT:{fmt(Panel_Temp,2)}, "
        f"BattT:{fmt(Batt_Temp,2)}, "
        f"SinkT:{fmt(Sink_Temp,2)}, "
        f"PreDrv:{fmt(Pre_Driver)}, "
        f"AuxI:{fmt(AuxI)}A"
    )

    line = "DATA,{},{},{},{},{},{}\n".format(TestV, TestI, AuxI, Sink_Temp, Batt_Temp, I_SET_POT_V)
    print (line)
    uart.write(line)

    print(output)
    if DEBUG_DAC:
        if DAC_Write_OK:
            print(
                "DAC DEBUG -> pot_read={}V, command={}V, code={}, attempts={}".format(
                    fmt(I_SET_POT_V), fmt(DAC_Command_V), DAC_Code, DAC_Write_Attempts
                )
            )
        else:
            print(
                "DAC ERROR -> pot_read={}V, command={}V, code={}, attempts={}, last_error={}".format(
                    fmt(I_SET_POT_V), fmt(DAC_Command_V), DAC_Code, DAC_Write_Attempts, DAC_Write_Error
                )
            )
    time.sleep(0.5)

    # line = "DATA,1,2,3,4,5,6\n"
    # uart.write(line)
    # time.sleep(0.5)
