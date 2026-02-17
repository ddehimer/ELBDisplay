from machine import I2C, Pin
import time

# ============================================================
# I2C SETUP
# ============================================================
i2c = I2C(
    0,
    sda=Pin(4),
    scl=Pin(5),
    freq=100_000
)

# ============================================================
# ADS1115 SETUP
# ============================================================
ADS_ADDR = 0x4A          # <-- use the address from i2c.scan()
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# Gain ±4.096 V (125 µV / LSB)
ADC_LSB = 4.096 / 32768

# AIN2 -> GND, single-shot, 128 SPS, ±4.096 V
# MUX = 110 (AIN2), PGA = 001
CONFIG_AIN2 = 0xE383

# ============================================================
# HALL SENSOR CALIBRATION
# ============================================================
HALL_TURNS = 10

# Measured from your data:
# ~6 mV @ 0.04 A with 10 turns
HALL_MV_PER_AMP_PER_TURN = 15.0
HALL_V_PER_AMP = (HALL_MV_PER_AMP_PER_TURN * HALL_TURNS) / 1000.0

# ============================================================
# ADC READ
# ============================================================
def read_uout():
    i2c.writeto_mem(
        ADS_ADDR,
        REG_CONFIG,
        CONFIG_AIN2.to_bytes(2, "big")
    )
    time.sleep_ms(8)

    data = i2c.readfrom_mem(ADS_ADDR, REG_CONVERSION, 2)
    raw = int.from_bytes(data, "big")
    if raw & 0x8000:
        raw -= 65536

    return raw * ADC_LSB

# ============================================================
# ZERO OFFSET CALIBRATION
# ============================================================
print("Calibrating zero offset — ensure NO current")
time.sleep(2)

samples = 50
v_sum = 0.0
for _ in range(samples):
    v_sum += read_uout()
    time.sleep_ms(5)

UOUT_ZERO = v_sum / samples
print(f"Zero offset stored: {UOUT_ZERO:.6f} V")
print("----------------------------------------")

# ============================================================
# MAIN LOOP
# ============================================================
while True:
    uout = read_uout()
    dv = uout - UOUT_ZERO
    current = -1* (dv / HALL_V_PER_AMP)

    print(f"Uout    : {uout:.6f} V")
    print(f"ΔV      : {dv*1000:.3f} mV")
    print(f"Current : {current:.4f} A")
    print("----------------------------------------")

    time.sleep(1)
