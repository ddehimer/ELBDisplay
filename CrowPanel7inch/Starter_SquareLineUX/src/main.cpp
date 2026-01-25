#include <PCA9557.h>
#include <lvgl.h>
#include <Crowbits_DHT20.h>

#include <SPI.h>
#include <Adafruit_GFX.h>

#include "lgfx/lgfx.h"
#include "ui.h"

void setup()
{
  delay(1000);

  // USB debug serial
  Serial.begin(115200);
  delay(2000);
  Serial.println("ESP32 ready");
  Serial.println("Running setup...");

  // UART to RP2040
  Serial1.begin(
    115200,
    SERIAL_8N1,
    16,   // RX pin from RP2040 TX
    17    // TX pin to RP2040 RX
  );
  Serial.println("UART1 ready");

  // Setup the panel / LVGL driver wrapper
  lcd.setup();

  // Initialize the SquareLine UI (creates screens/objects and loads the screen)
  ui_init();

  // Kick LVGL once
  lv_timer_handler();
}

void loop()
{
  // Keep UI alive
  lv_timer_handler();

  // ---- RP2040 UART receive ----
  while (Serial1.available())
  {
    char c = Serial1.read();
    Serial.write(c);   // echo to USB for now
  }

  delay(5);
}
