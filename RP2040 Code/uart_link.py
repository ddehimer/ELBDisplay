from machine import UART, Pin

uart = UART(
    0,
    baudrate=115200,
    tx=Pin(0),
    rx=Pin(1)
)

def send(msg):
    uart.write(msg + "\n")

def receive():
    if uart.any():
        data = uart.readline()
        if data:
            return data.decode().strip()
    return None

