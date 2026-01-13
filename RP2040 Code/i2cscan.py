from machine import Pin, I2C

i2c = I2C(
    0,                 # ← MUST be I2C(0) for GPIO4/5
    sda=Pin(4),
    scl=Pin(5),
    freq=100_000       # start slow for bring-up
)

devices = i2c.scan()

print("I2C devices:", [hex(d) for d in devices])