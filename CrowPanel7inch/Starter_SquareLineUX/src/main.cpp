#include <PCA9557.h>
#include <lvgl.h>
#include <Crowbits_DHT20.h>

#include <SPI.h>
#include <Adafruit_GFX.h>

#include "lgfx/lgfx.h"
#include "ui.h"

// ----------------------------------------------------
// On-screen keyboard callback (TextArea -> Keyboard)
// ----------------------------------------------------
static void textarea_event_cb(lv_event_t * e)
{
  lv_event_code_t code = lv_event_get_code(e);
  lv_obj_t * ta = (lv_obj_t *)lv_event_get_target(e);

  // Show keyboard when textarea is focused or clicked
  if (code == LV_EVENT_FOCUSED || code == LV_EVENT_CLICKED)
  {
    lv_keyboard_set_textarea(ui_Keyboard3, ta);
    lv_obj_clear_flag(ui_Keyboard3, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(ui_Keyboard3);
  }

  // Hide keyboard when user finishes or cancels input
  if (code == LV_EVENT_READY || code == LV_EVENT_CANCEL || code == LV_EVENT_DEFOCUSED)
  {
    lv_obj_add_flag(ui_Keyboard3, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_state(ta, LV_STATE_FOCUSED);
  }
}

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

  // Initialize the SquareLine UI
  ui_init();

  // -----------------------------
  // Keyboard setup
  // -----------------------------
  // Hide keyboard at startup
  lv_obj_add_flag(ui_Keyboard3, LV_OBJ_FLAG_HIDDEN);

  // Link keyboard to your TextAreas
  lv_obj_add_event_cb(ui_FIle_Name, textarea_event_cb, LV_EVENT_ALL, NULL);
  lv_obj_add_event_cb(ui_Date, textarea_event_cb, LV_EVENT_ALL, NULL);

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
