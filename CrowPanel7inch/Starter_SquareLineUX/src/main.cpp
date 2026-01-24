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
  Serial.begin(115200);
  delay(2000);

  Serial.println("Running setup...");

  // Setup the panel / LVGL driver wrapper
  lcd.setup();

  // Initialize the SquareLine UI (creates screens/objects and loads the screen)
  ui_init();

  // Kick LVGL once
  lv_timer_handler();
}

void loop()
{
  lv_timer_handler();
  delay(5);
}
