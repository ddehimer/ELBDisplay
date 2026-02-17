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
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100_000)

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

# ============================================================
# ADS READ FUNCTION
# ============================================================
def read_ads(addr, channel):
    config = 0x8000 | MUX[channel] | BASE_CONFIG
    i2c.writeto_mem(addr, REG_CONFIG, config.to_bytes(2, "big"))
    time.sleep_ms(8)

    data = i2c.readfrom_mem(addr, REG_CONVERSION, 2)
    raw = int.from_bytes(data, "big")

    if raw & 0x8000:
        raw -= 65536

    return raw * ADC_LSB

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

    AuxI = -1* ((Aux_V - UOUT_ZERO) / HALL_V_PER_AMP)
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
        f"5VR:{fmt(VR_5V)}, "
        f"PanelT:{fmt(Panel_Temp,2)}, "
        f"BattT:{fmt(Batt_Temp,2)}, "
        f"SinkT:{fmt(Sink_Temp,2)}, "
        f"PreDrv:{fmt(Pre_Driver)}, "
        f"AuxI:{fmt(AuxI)}A"
    )

    line = "DATA,{},{},{},{},{},{},{}\n".format(TestV, TestI, TestV*TestI, AuxI, Sink_Temp, Batt_Temp, I_SET_POT_V)
    print (line)
    uart.write(line)

    print(output)
    time.sleep(1)
