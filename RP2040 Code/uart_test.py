from machine import UART, Pin
import time
import math

# UART0 pins: TX=GP0, RX=GP1
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

t = 0.0
while True:
    # Keep values inside chart ranges
    tb1 = int(12 + 2 * math.sin(t))        # 0-15
    tb2 = int(10 + 2 * math.cos(t))        # 0-12
    shunt = int(100 + 50 * math.sin(t*0.7))# 0-200
    aux = int(6 + 3 * math.sin(t*1.3))     # 0-12
    t1 = int(80 + 40 * math.sin(t*0.5))    # 0-200
    t2 = int(70 + 30 * math.cos(t*0.9))    # 0-200

    line = "DATA,{},{},{},{},{},{}\n".format(tb1, tb2, shunt, aux, t1, t2)
    print (line)
    uart.write(line)

    t += 0.2
    time.sleep(0.5)