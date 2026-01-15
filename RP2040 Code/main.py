from machine import Pin
import time

led = Pin(25, Pin.OUT)

count = 0

while count<5:
    led.toggle()
    time.sleep(0.5)
    count += 1

import temptest