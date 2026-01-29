from machine import I2C, Pin
import time

from drivers.ads1115 import ADS1115
from drivers.current_dac import CurrentDAC
from current_control import CurrentController

print("=== RP2040 BOOTED ===")

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100_000)

adc = ADS1115(i2c)
dac = CurrentDAC(i2c)

controller = CurrentController(adc, dac)
controller.start_mode = True   # FORCE start mode for now

while True:
    controller.update()
    time.sleep(1)
