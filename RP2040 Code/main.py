from machine import Pin
import time

led = Pin(25, Pin.OUT)

def main():
    try:
        while True:
            led.toggle()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Main loop stopped")

if __name__ == "__main__":
    main()