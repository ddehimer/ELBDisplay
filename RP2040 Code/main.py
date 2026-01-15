from machine import Pin
import time
import i2cscan
import temptest

led = Pin(25, Pin.OUT)

while True:
    led.toggle()
    time.sleep(0.5)