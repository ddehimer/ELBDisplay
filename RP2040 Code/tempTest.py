from machine import I2C, Pin
import time
import math

# ---------------- I2C SETUP ----------------
i2c = I2C(
    0,
    sda=Pin(4),
    scl=Pin(5),
    freq=100_000
)

ADS_ADDR = 0x4A  # ADDR tied to SDA

# ADS1115 registers
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# AIN0 single-ended, ±6.144V, single-shot, 128 SPS
CONFIG_AIN0 = 0xD183

# ---------------- HARDWARE CONSTANTS ----------------
R_FIXED  = 4990.0     # R18, ohms
V_SUPPLY = 4.3        # +5V_VR is actually 4.3V

# Thermistor (from measurement)
R0   = 12000         # ohms @ 25C
T0   = 298.15         # Kelvin (25C)
BETA = 3950.0         # reasonable starting value

# ---------------- FUNCTIONS ----------------
def read_vadc():
    # Start conversion
    i2c.writeto_mem(
        ADS_ADDR,
        REG_CONFIG,
        bytes([(CONFIG_AIN0 >> 8) & 0xFF, CONFIG_AIN0 & 0xFF])
    )

    time.sleep_ms(10)

    data = i2c.readfrom_mem(ADS_ADDR, REG_CONVERSION, 2)
    raw = (data[0] << 8) | data[1]

    if raw & 0x8000:
        raw -= 65536

    # ±6.144 V range
    voltage = raw * 6.144 / 32768
    return voltage


def read_heatsink_temp_c():
    v = read_vadc()

    # sanity check
    if v <= 0.01 or v >= (V_SUPPLY - 0.01):
        return None, None, v

    # Thermistor resistance
    r_ntc = R_FIXED * (V_SUPPLY - v) / v

    # Beta equation
    temp_k = 1.0 / (
        (1.0 / T0) +
        (1.0 / BETA) * math.log(r_ntc / R0)
    )

    temp_c = temp_k - 273.15
    return temp_c, r_ntc, v


# ---------------- MAIN LOOP ----------------
while True:
    temp_c, r_ntc, v = read_heatsink_temp_c()

    if temp_c is None:
        print(f"ADC out of range: V={v:.3f} V")
    else:
        print(
            f"Heatsink: {temp_c:6.2f} °C | "
            f"R_ntc={r_ntc:7.0f} Ω | "
            f"Vadc={v:4.3f} V"
        )

    time.sleep(10)
