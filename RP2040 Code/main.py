from uart_link import send, receive
import time

print("RP2040 ready")

while True:
    cmd = receive()
    if cmd:
        print("RX:", cmd)
        send("ECHO:" + cmd)
    time.sleep(0.1)
