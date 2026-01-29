from machine import UART, Pin
import time

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

def send(msg):
    uart.write((msg + "\n").encode("utf-8"))

def receive():
    if uart.any():
        data = uart.readline()
        if isinstance(data, bytes):
            return data.decode("utf-8").strip()
    return None

send("RP2040_READY")

while True:
    cmd = receive()
    if cmd:
        send("ECHO:" + cmd)
    time.sleep(0.1)
