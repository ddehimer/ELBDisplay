# ============================================================
# main.py
#
# High-level application entry point for RP2040 system
#
# Responsibilities:
# - Initialize all hardware interfaces
# - Own and manage application state
# - Run the main event loop
# - Coordinate work done by other modules
#
# This file intentionally does NOT:
# - Contain sensor math
# - Contain SD card file logic
# - Contain display formatting
#
# Those responsibilities belong in separate modules
# ============================================================

from machine import Pin, I2C, UART, SPI
import time


# ============================================================
# Application States
#
# The system is intentionally state-driven.
# This avoids large, fragile if/else logic and makes
# start/stop behavior explicit and testable.
#
# IDLE:
#   - System powered
#   - No logging occurring
#
# LOGGING:
#   - Sensors are sampled
#   - Data is sent to display
#   - Data is written to SD card
# ============================================================

STATE_IDLE = 0
STATE_LOGGING = 1


# ============================================================
# Hardware Initialization Functions
#
# Each init function:
# - Owns exactly one hardware interface
# - Is called once at boot
# - Returns a configured object for use elsewhere
#
# This keeps pin configuration out of application logic
# and makes future refactors painless.
# ============================================================

def init_i2c():
    """
    Initialize I2C bus used for external ADCs.
    """
    return I2C(
        0,
        scl=Pin(17),
        sda=Pin(16),
        freq=400_000
    )


def init_uart():
    """
    Initialize UART used to communicate with the Elecrow display / ESP32.
    """
    return UART(
        1,
        baudrate=115200,
        tx=Pin(4),
        rx=Pin(5)
    )


def init_spi():
    """
    Initialize SPI bus used for the MicroSD card.
    """
    return SPI(
        0,
        baudrate=10_000_000,
        polarity=0,
        phase=0,
        sck=Pin(18),
        mosi=Pin(19),
        miso=Pin(16)
    )


def init_gpio():
    """
    Initialize simple GPIO used for local control and debugging.
    The button currently simulates a start/stop event.
    """
    button = Pin(20, Pin.IN, Pin.PULL_UP)
    led = Pin(25, Pin.OUT)
    return button, led


# ============================================================
# Main Application Function
#
# This is the orchestrator:
# - Initializes the system
# - Owns the current state
# - Runs forever
#
# All real work is delegated to helper functions or modules.
# ============================================================

def main():
    print("System booting...")

    # --- Hardware Setup ---
    i2c = init_i2c()
    uart = init_uart()
    spi = init_spi()
    button, led = init_gpio()

    # --- Initial State ---
    state = STATE_IDLE
    led.off()

    print("Initialization complete")

    # ========================================================
    # Main Loop
    #
    # This loop is intentionally simple:
    # - Evaluate current state
    # - Perform actions for that state
    # - Check for state transitions
    #
    # No blocking operations should live here long-term.
    # ========================================================

    while True:
        if state == STATE_IDLE:
            # ------------------------------------------------
            # IDLE STATE
            #
            # System is waiting for a start event.
            # No sensor reads or SD writes occur here.
            # ------------------------------------------------
            led.off()

            # Button press simulates a "start logging" command
            if not button.value():
                print("Logging started")
                state = STATE_LOGGING
                time.sleep_ms(300)  # debounce

        elif state == STATE_LOGGING:
            # ------------------------------------------------
            # LOGGING STATE
            #
            # This is where:
            # - Sensors will be sampled
            # - Data will be sent to the display
            # - Data will be written to the SD card
            #
            # Actual implementations will live in modules.
            # ------------------------------------------------
            led.on()

            # Placeholder calls (to be added later):
            # read_all_sensors(i2c)
            # send_data_to_display(uart)
            # log_data_to_sd(spi)

            # Button press simulates a "stop logging" command
            if not button.value():
                print("Logging stopped")
                state = STATE_IDLE
                time.sleep_ms(300)  # debounce

        # Small delay to prevent maxing CPU and to stabilize inputs
        time.sleep_ms(50)


# ============================================================
# Program Entry Point
#
# Ensures this file can be imported without immediately running
# the application logic (important for testing and reuse).
# ============================================================

if __name__ == "__main__":
    main()
