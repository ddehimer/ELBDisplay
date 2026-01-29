#include <PCA9557.h>
#include <lvgl.h>
#include <Crowbits_DHT20.h>

#include <SPI.h>
#include <Adafruit_GFX.h>

#include "lgfx/lgfx.h"
#include "ui.h"
#include "screens/ui_Screen1.h"

#include "sd_export.h"


// ----------------------------------------------------
// Globals
// ----------------------------------------------------
static bool g_sd_ok = false; // track whether SD card mounted successfully

// ----------------------------------------------------
// Export button callback
// ----------------------------------------------------
static void export_event_cb(lv_event_t* e)
{
  if (lv_event_get_code(e) != LV_EVENT_CLICKED) return;

  const char* name = lv_textarea_get_text(ui_File_Name);
  const char* date = lv_textarea_get_text(ui_Date);

  if (!g_sd_ok)
  {
    Serial.println("❌ Export blocked: SD not mounted / not detected.");
    return;
  }

  if (!name || name[0] == '\0')
  {
    Serial.println("❌ Enter a file name before exporting.");
    return;
  }

  if (!date || date[0] == '\0')
  {
    Serial.println("❌ Enter a date before exporting.");
    return;
  }

bool ok = sd_export_chart_csv_first_series(name, date, "shunt", ui_Chart6);


  if (ok) Serial.println("✅ Export success (CSV written to SD).");
  else    Serial.println("❌ Export failed.");
}

// ----------------------------------------------------
// On-screen keyboard callback (TextArea -> Keyboard)
// ----------------------------------------------------
static void textarea_event_cb(lv_event_t * e)
{
  lv_event_code_t code = lv_event_get_code(e);
  lv_obj_t * ta = (lv_obj_t *)lv_event_get_target(e);

  // Show keyboard when textarea is tapped
  if (code == LV_EVENT_CLICKED || code == LV_EVENT_FOCUSED)
  {
    lv_obj_add_state(ta, LV_STATE_FOCUSED);
    lv_keyboard_set_textarea(ui_Keyboard3, ta);
    lv_obj_clear_flag(ui_Keyboard3, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(ui_Keyboard3);
  }

  // Hide keyboard ONLY when user finishes or cancels
  if (code == LV_EVENT_READY || code == LV_EVENT_CANCEL)
  {
    lv_obj_add_flag(ui_Keyboard3, LV_OBJ_FLAG_HIDDEN);
    lv_keyboard_set_textarea(ui_Keyboard3, NULL);
    lv_obj_clear_state(ta, LV_STATE_FOCUSED);
  }
}


void setup()
{
  delay(1000);

  Serial.begin(115200);
  delay(2000);
  Serial.println("ESP32 ready");
  Serial.println("Running setup...");

  Serial1.begin(
    115200,
    SERIAL_8N1,
    16,
    17
  );
  Serial.println("UART1 ready");

  // Display/LVGL init (touch too)
  lcd.setup();

  // UI init (SquareLine)
  ui_init();

  // SD init
  g_sd_ok = sd_init();
  Serial.printf("SD status: %s\n", g_sd_ok ? "OK" : "NOT OK");

  // -----------------------------
  // Keyboard setup
  // -----------------------------
  lv_obj_add_flag(ui_Keyboard3, LV_OBJ_FLAG_HIDDEN);

  lv_obj_add_event_cb(ui_File_Name, textarea_event_cb, LV_EVENT_ALL, NULL);
  lv_obj_add_event_cb(ui_Date,      textarea_event_cb, LV_EVENT_ALL, NULL);

  // -----------------------------
  // Export button hookup
  // -----------------------------
  lv_obj_add_event_cb(ui_Button1, export_event_cb, LV_EVENT_CLICKED, NULL);

  lv_timer_handler();
}

void loop()
{
  lv_timer_handler();

  while (Serial1.available())
  {
    char c = Serial1.read();
    Serial.write(c);
  }

  delay(5);
}
