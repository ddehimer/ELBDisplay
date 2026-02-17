from machine import I2C, Pin
import time
import math

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

# PGA ±4.096V (125 µV/LSB)
PGA_4_096 = 0x0200
MODE_SINGLE = 0x0100
DR_128SPS = 0x0080
COMP_DISABLE = 0x0003

BASE_CONFIG = PGA_4_096 | MODE_SINGLE | DR_128SPS | COMP_DISABLE

ADC_LSB = 4.096 / 32768  # volts per bit

# ============================================================
# THERMISTOR CONSTANTS
# ============================================================
R_FIXED  = 4990.0
V_SUPPLY = 4.3

R0   = 12000
T0   = 298.15
BETA = 3950.0

# ============================================================
# HALL SENSOR CONSTANT
# ============================================================
HALL_V_PER_AMP = 0.150  # <-- USE YOUR MEASURED VALUE

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
# THERMISTOR FUNCTION (SAFE)
# ============================================================
def thermistor_temp(v_adc):
    if v_adc <= 0 or v_adc >= V_SUPPLY:
        return None

    r = (R_FIXED * v_adc) / (V_SUPPLY - v_adc)
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
        total += read_ads(0x4A, 3)  # Aux_I = 0x4A AIN3
        time.sleep_ms(5)

    zero = total / samples
    print("Zero offset:", zero)
    print("----------------------------------")
    return zero

# ============================================================
# STARTUP CALIBRATION
# ============================================================
UOUT_ZERO = calibrate_aux()

# ============================================================
# MAIN LOOP
# ============================================================
while True:

    # -------- 0x48 --------
    V_Sense     = read_ads(0x48, 0)
    Test_V1_Div = read_ads(0x48, 1)
    Power_V     = read_ads(0x48, 2)
    Driver_V    = read_ads(0x48, 3)

    # -------- 0x49 --------
    Pyranometer = read_ads(0x49, 0)
    I_SET_POT_V = read_ads(0x49, 1)
    VR_5V       = read_ads(0x49, 2)
    Panel_T_V   = read_ads(0x49, 3)

    # -------- 0x4A --------
    Batt_T_V    = read_ads(0x4A, 0)
    Sink_T_V    = read_ads(0x4A, 1)
    Pre_Driver  = read_ads(0x4A, 2)
    Aux_V       = read_ads(0x4A, 3)

    # -------- Conversions --------
    Panel_Temp = thermistor_temp(Panel_T_V)
    Batt_Temp  = thermistor_temp(Batt_T_V)
    Sink_Temp  = thermistor_temp(Sink_T_V)

    Aux_Current = (Aux_V - UOUT_ZERO) / HALL_V_PER_AMP

    I_SET_Percent = (I_SET_POT_V / 5.0) * 100.0

    # -------- Output --------
    output = (
        f"VS:{fmt(V_Sense)}, "
        f"TV1:{fmt(Test_V1_Div)}, "
        f"PV:{fmt(Power_V)}, "
        f"DV:{fmt(Driver_V)}, "
        f"PYR:{fmt(Pyranometer)}, "
        f"POT%:{fmt(I_SET_Percent,1)}, "
        f"5VR:{fmt(VR_5V)}, "
        f"PanelT:{fmt(Panel_Temp,2)}, "
        f"BattT:{fmt(Batt_Temp,2)}, "
        f"SinkT:{fmt(Sink_Temp,2)}, "
        f"PreDrv:{fmt(Pre_Driver)}, "
        f"AuxI:{fmt(Aux_Current)}A"
    )

    print(output)
    time.sleep(1)
