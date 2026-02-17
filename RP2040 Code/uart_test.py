from machine import UART, Pin
import time
import math

# UART0 pins: TX=GP0, RX=GP1
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

t = 0.0
while True:
    # Keep values inside chart ranges
    tb1 = round(12 + 2 * math.sin(t), 3)         # 0-15
    tb2 = round(10 + 2 * math.cos(t), 3)         # 0-12
    shunt = round(100 + 50 * math.sin(t * 0.7), 3) # 0-200
    aux = round(6 + 3 * math.sin(t * 1.3), 3)    # 0-12
    t1 = round(80 + 40 * math.sin(t * 0.5), 3)   # 0-200
    t2 = round(70 + 30 * math.cos(t * 0.9), 3)   # 0-200
    pot = round(10 + 8 * math.sin(t * 1.1), 3)   # 0-20

    line = "DATA,{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f}\n".format(
        tb1, tb2, shunt, aux, t1, t2, pot
    )
    print(line)
    uart.write(line)

    t += 0.2
    time.sleep(0.5)