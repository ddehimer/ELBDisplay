from machine import I2C, Pin
import time

def dac_write(code):
    code = max(0, min(4095, int(code)))
    cmd = 0x40              # Fast write
    msb = (code >> 4) & 0xFF
    lsb = (code & 0x0F) << 4
    i2c.writeto(0x60, bytes([cmd, msb, lsb]))


i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100_000)

print("I2C scan:", i2c.scan())

while True:
    print("DAC = 0")
    dac_write(0)
    time.sleep(3)

    print("DAC = mid")
    dac_write(2048)
    time.sleep(3)

    print("DAC = full")
    dac_write(4095)
    time.sleep(3)
