# ELBDisplay

# System Architecture Overview

## Purpose

This document describes the high-level software architecture for the dual-MCU system consisting of an RP2040 and an ESP32 (Elecrow display). It defines responsibilities, data flow, and communication contracts to ensure a shared understanding and long-term maintainability.

---

## System Overview

The system is split into two logical nodes:

* **RP2040**: Deterministic data acquisition and control
* **ESP32 (Elecrow Display)**: User interface, system control, and SD card data logging

The nodes communicate over a **UART** connection using a simple, line-based ASCII protocol.

---

## High-Level Data Flow

Sensors → ADCs → RP2040 → UART → ESP32 → Display
↓
SD Card (CSV)

Control commands flow in the opposite direction:

User Input → ESP32 → UART → RP2040

---

## RP2040 Responsibilities (Data & Control Node)

### Primary Responsibilities

* Read sensor values via I2C ADCs
* Apply calibration and unit conversion
* Maintain deterministic sampling timing
* Stream live data to the ESP32 over UART
* Respond to control commands (start/stop)

### Explicitly Out of Scope

* SD card access or file handling
* UI logic or display management

### Runtime Model

* Non-blocking main loop
* State machine-driven behavior

  * `IDLE`
  * `ACTIVE`
  * `ERROR`

### Outputs

* Periodic `DATA` messages
* `STATUS` updates
* `ERROR` notifications

---

## ESP32 Responsibilities (UI & Storage Node)

### Primary Responsibilities

* Touch UI and display rendering (LVGL / SquareLine)
* User interaction (start/stop, filename entry)
* UART communication with RP2040
* CSV file creation and data logging to SD card
* Display of live data, system state, and errors

### Runtime Model

* Event-driven UI callbacks
* Dedicated UART RX/TX task
* UI state mirrors RP2040 operational state

### Storage Model

* SD card mounted on ESP32
* CSV files created per logging session
* Data appended as received from RP2040

---

## UART Communication Contract

### Message Characteristics

* ASCII text
* Line-delimited (`\n`)
* Human-readable for debugging

### ESP32 → RP2040 Commands

* `START`
* `STOP`
* Configuration or control commands (future expansion)

### RP2040 → ESP32 Messages

* `DATA,<value1>,<value2>,...`
* `STATUS,<state>`
* `ERROR,<error_code>`

---

## Timing & Ownership

| Function        | Owner  |
| --------------- | ------ |
| Sensor sampling | RP2040 |
| Data processing | RP2040 |
| SD card writing | ESP32  |
| UI interaction  | ESP32  |
| System control  | ESP32  |

---

## Architectural Benefits

* Clear separation of concerns
* Deterministic data acquisition preserved
* UI and storage failures isolated from sensing
* Simple, debuggable communication protocol
* Scalable for additional sensors or UI features

---

## Summary

This architecture cleanly separates real-time data acquisition from user interaction and storage concerns. By assigning deterministic tasks to the RP2040 and UI/storage tasks to the ESP32, the system remains robust, scalable, and maintainable while supporting future expansion.
