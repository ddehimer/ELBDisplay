#include <PCA9557.h>
#include <lvgl.h>
#include <Crowbits_DHT20.h>

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <stdio.h>
#include <stdarg.h>
#include <limits.h>
#include <math.h>

#include "lgfx/lgfx.h"
#include "ui.h"
#include "screens/ui_Screen1.h"

#include "sd_export.h"
#include "data_model.h"


// ----------------------------------------------------
// Globals
// ----------------------------------------------------
static bool g_sd_ok = false; // track whether SD card mounted successfully
static uint32_t g_last_sample_ms = 0;
static uint32_t g_boot_ms = 0;
static bool g_sd_status_printed = false;
static uint32_t g_last_sd_poll_ms = 0;
static uint32_t g_export_status_reset_ms = 0;
static float g_last_ui_tbv = NAN;
static float g_last_ui_tbc = NAN;
static float g_last_ui_power = NAN;
static float g_last_ui_ab = NAN;
static float g_last_ui_hst = NAN;
static float g_last_ui_tbt = NAN;
static float g_last_ui_pot = NAN;

// Latest UART data (RP2040) for ring buffer sampling
static bool g_has_uart_sample = false;
static float g_last_tb1 = 0.0f;
static float g_last_tb2 = 0.0f;
static float g_last_power_w = 0.0f;
static float g_last_aux = 0.0f;
static float g_last_t1 = 0.0f;
static float g_last_t2 = 0.0f;
static float g_last_pot = 0.0f;

// ----------------------------------------------------
// UART data parser (RP2040 -> ESP32)
// Expected line: DATA,<tb_v>,<tb_a>,<aux_a>,<sink_t_c>,<batt_t_c>,<pot_v>\n
// ----------------------------------------------------
static constexpr size_t UART_LINE_MAX = 96;
static char g_uart_line[UART_LINE_MAX];
static size_t g_uart_len = 0;

static lv_chart_series_t* chart_series_by_index(lv_obj_t* chart, uint16_t idx);

static void diag_line(const char* msg)
{
  Serial.println(msg);
}

static void diag_printf(const char* fmt, ...)
{
  char buf[160];
  va_list args;
  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  Serial.print(buf);
}

static void ui_set_status_label(lv_obj_t* label, const char* text, lv_color_t color)
{
  if (!label || !text) return;
  lv_label_set_text(label, text);
  lv_obj_set_style_text_color(label, color, LV_PART_MAIN | LV_STATE_DEFAULT);
}

static void ui_set_sd_status(bool ready)
{
  if (ready) {
    ui_set_status_label(ui_SDCardStatus, "SD Card Status: Ready", lv_palette_main(LV_PALETTE_GREEN));
  } else {
    ui_set_status_label(ui_SDCardStatus, "SD Card Status: Not Ready", lv_palette_main(LV_PALETTE_RED));
  }
}

static void ui_set_export_status_idle()
{
  ui_set_status_label(ui_ExportStatus, "Export Status: Idle", lv_palette_main(LV_PALETTE_GREY));
}

static void ui_set_export_status_ok()
{
  ui_set_status_label(ui_ExportStatus, "Export Status: Success", lv_palette_main(LV_PALETTE_GREEN));
}

static void ui_set_export_status_error(const char* reason)
{
  char buf[96];
  snprintf(buf, sizeof(buf), "Export Status: %s", reason ? reason : "Failed");
  ui_set_status_label(ui_ExportStatus, buf, lv_palette_main(LV_PALETTE_RED));
}

static void ui_schedule_export_status_idle(uint32_t now_ms)
{
  g_export_status_reset_ms = now_ms + 10000UL;
}

static void chart_push_value(lv_obj_t* chart, uint16_t series_idx, float v)
{
  lv_chart_series_t* series = chart_series_by_index(chart, series_idx);
  if (!series) return;
  lv_chart_set_next_value(chart, series, (lv_coord_t)lroundf(v));
}

static bool value_changed(float a, float b)
{
  return isnan(a) || fabsf(a - b) >= 0.0005f;
}

static void ui_set_value_label(lv_obj_t* label, float value, const char* unit)
{
  if (!label || !unit) return;

  const int32_t scaled = (int32_t)lroundf(value * 1000.0f);
  const bool neg = (scaled < 0);
  const int32_t abs_scaled = neg ? -scaled : scaled;
  const int32_t whole = abs_scaled / 1000;
  const int32_t frac = abs_scaled % 1000;

  char buf[40];
  if (neg) {
    snprintf(buf, sizeof(buf), "-%ld.%03ld%s", (long)whole, (long)frac, unit);
  } else {
    snprintf(buf, sizeof(buf), "%ld.%03ld%s", (long)whole, (long)frac, unit);
  }

  lv_label_set_text(label, buf);
}

static void ui_sync_test_battery_title_values()
{
  const float tbv = g_last_tb1;
  const float tbc = g_last_tb2;
  const float power = g_last_power_w;
  const float ab = g_last_aux;
  const float hst = g_last_t1;
  const float tbt = g_last_t2;
  const float pot = g_last_pot;

  if (value_changed(g_last_ui_tbv, tbv)) {
    ui_set_value_label(ui_TBVvalue, tbv, " V");
    g_last_ui_tbv = tbv;
  }

  if (value_changed(g_last_ui_tbc, tbc)) {
    ui_set_value_label(ui_TBCvalue, tbc, " A");
    g_last_ui_tbc = tbc;
  }

  if (value_changed(g_last_ui_power, power)) {
    ui_set_value_label(ui_Pvalue, power, " W");
    g_last_ui_power = power;
  }

  if (value_changed(g_last_ui_ab, ab)) {
    ui_set_value_label(ui_ABvalue, ab, " A");
    g_last_ui_ab = ab;
  }

  if (value_changed(g_last_ui_hst, hst)) {
    ui_set_value_label(ui_HSTvalue, hst, " C");
    g_last_ui_hst = hst;
  }

  if (value_changed(g_last_ui_tbt, tbt)) {
    ui_set_value_label(ui_TBTvalue, tbt, " C");
    g_last_ui_tbt = tbt;
  }

  if (value_changed(g_last_ui_pot, pot)) {
    ui_set_value_label(ui_Potvalue, pot, " A");
    g_last_ui_pot = pot;
  }

  if (ui_Bar2) {
    int16_t bar_v = (int16_t)lroundf(pot);
    if (bar_v < 0) bar_v = 0;
    if (bar_v > 20) bar_v = 20;
    lv_bar_set_value(ui_Bar2, bar_v, LV_ANIM_OFF);
  }
}

static bool parse_data_line(const char* line,
                            float& tb_v, float& tb_a,
                            float& aux_a, float& sink_t_c, float& batt_t_c, float& pot_v)
{
  if (!line) return false;
  if (strncmp(line, "DATA,", 5) != 0) return false;

  float v1, v2, v3, v4, v5, v6;
  int n = sscanf(line + 5, "%f,%f,%f,%f,%f,%f", &v1, &v2, &v3, &v4, &v5, &v6);
  if (n != 6) return false;

  tb_v = roundf(v1 * 1000.0f) / 1000.0f;
  tb_a = roundf(v2 * 1000.0f) / 1000.0f;
  aux_a = roundf(v3 * 1000.0f) / 1000.0f;
  sink_t_c = roundf(v4 * 1000.0f) / 1000.0f;
  batt_t_c = roundf(v5 * 1000.0f) / 1000.0f;
  pot_v = roundf(v6 * 1000.0f) / 1000.0f;
  return true;
}

static void handle_uart_line(const char* line)
{
  float tb_v, tb_a, aux_a, sink_t_c, batt_t_c, pot_v;
  if (!parse_data_line(line, tb_v, tb_a, aux_a, sink_t_c, batt_t_c, pot_v)) return;

  // Update latest UART sample for ring buffer
  const float power_w = roundf((tb_v * tb_a) * 1000.0f) / 1000.0f;
  g_last_tb1 = tb_v;
  g_last_tb2 = tb_a;
  g_last_power_w = power_w;
  g_last_aux = aux_a;
  g_last_t1 = sink_t_c;
  g_last_t2 = batt_t_c;
  g_last_pot = pot_v;
  g_has_uart_sample = true;

  chart_push_value(ui_Chart2, 0, tb_v);
  chart_push_value(ui_Chart2, 1, tb_a);
  chart_push_value(ui_Chart6, 0, power_w);
  chart_push_value(ui_Chart1, 0, aux_a);
  chart_push_value(ui_Chart3, 0, sink_t_c);
  chart_push_value(ui_Chart3, 1, batt_t_c);

  lv_chart_refresh(ui_Chart2);
  lv_chart_refresh(ui_Chart6);
  lv_chart_refresh(ui_Chart1);
  lv_chart_refresh(ui_Chart3);
  ui_sync_test_battery_title_values();
}

static lv_chart_series_t* chart_series_by_index(lv_obj_t* chart, uint16_t idx)
{
  if (!chart) return NULL;

  lv_chart_series_t* series = NULL;
  for (uint16_t i = 0; i <= idx; i++) {
    series = lv_chart_get_series_next(chart, series);
    if (!series) return NULL;
  }
  return series;
}

static void chart_clear_all(lv_obj_t* chart)
{
  if (!chart) return;

  lv_chart_series_t* series = NULL;
  while ((series = lv_chart_get_series_next(chart, series)) != NULL)
  {
    lv_chart_set_all_value(chart, series, LV_CHART_POINT_NONE);
  }
  lv_chart_refresh(chart);
}

// ----------------------------------------------------
// Export button callback
// ----------------------------------------------------
static void export_event_cb(lv_event_t* e)
{
  if (lv_event_get_code(e) != LV_EVENT_CLICKED) return;
  const uint32_t now_ms = millis();

  const char* name = lv_textarea_get_text(ui_File_Name);
  const char* date = lv_textarea_get_text(ui_Date);

  if (!g_sd_ok)
  {
    Serial.println("Export blocked: SD not mounted / not detected.");
    ui_set_export_status_error("No SD Card");
    ui_schedule_export_status_idle(now_ms);
    return;
  }

  if (!name || name[0] == '\0')
  {
    Serial.println("Enter a file name before exporting.");
    ui_set_export_status_error("Enter File Name");
    ui_schedule_export_status_idle(now_ms);
    return;
  }

  if (!date || date[0] == '\0')
  {
    Serial.println("Enter a date before exporting.");
    ui_set_export_status_error("Enter Date");
    ui_schedule_export_status_idle(now_ms);
    return;
  }

  bool ok = sd_export_combined_csv(name, date,
                                   ui_Chart2,
                                   ui_Chart6,
                                   ui_Chart1,
                                   ui_Chart3);


  if (ok) {
    Serial.println("Export success (CSV written to SD).");
    ui_set_export_status_ok();
    ui_schedule_export_status_idle(now_ms);
  } else {
    Serial.println("Export failed.");
    ui_set_export_status_error("Failed");
    ui_schedule_export_status_idle(now_ms);
  }
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
  diag_line("ESP32 ready");
  diag_line("Running setup...");

  Serial1.begin(
    115200,
    SERIAL_8N1,
    44,
    43
  );
  diag_line("UART1 ready");

  // Display/LVGL init (touch too)
  lcd.setup();

  // UI init (SquareLine)
  ui_init();
  dm_init();
  g_last_sample_ms = millis();

  // Clear chart placeholders so UART data is the only visible source
  chart_clear_all(ui_Chart2);
  chart_clear_all(ui_Chart6);
  chart_clear_all(ui_Chart1);
  chart_clear_all(ui_Chart3);
  ui_sync_test_battery_title_values();

  // SD init
  ui_set_status_label(ui_SDCardStatus, "SD Card Status: Checking...", lv_palette_main(LV_PALETTE_ORANGE));
  g_sd_ok = sd_init();
  ui_set_sd_status(g_sd_ok);
  ui_set_export_status_idle();
  g_export_status_reset_ms = 0;
  diag_printf("SD status: %s\n", g_sd_ok ? "OK" : "NOT OK");
  Serial.flush();

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

  g_boot_ms = millis();
  g_last_sd_poll_ms = g_boot_ms;
  g_sd_status_printed = false;
}

void loop()
{
  lv_timer_handler();
  ui_sync_test_battery_title_values();
  const uint32_t now = millis();

  if ((now - g_last_sd_poll_ms) >= 1000UL)
  {
    g_last_sd_poll_ms = now;
    const bool sd_now_ok = sd_is_ready();
    if (sd_now_ok != g_sd_ok)
    {
      g_sd_ok = sd_now_ok;
      ui_set_sd_status(g_sd_ok);
      if (!g_sd_ok) {
        ui_set_export_status_error("No SD Card");
        ui_schedule_export_status_idle(now);
      }
      diag_printf("SD status changed: %s\n", g_sd_ok ? "OK" : "NOT OK");
    }
  }

  if (g_export_status_reset_ms != 0 &&
      (int32_t)(now - g_export_status_reset_ms) >= 0)
  {
    ui_set_export_status_idle();
    g_export_status_reset_ms = 0;
  }

  if (!g_sd_status_printed && (millis() - g_boot_ms) >= 3000UL)
  {
    diag_printf("SD status (delayed): %s\n", g_sd_ok ? "OK" : "NOT OK");
    g_sd_status_printed = true;
  }

  if ((now - g_last_sample_ms) >= 5000UL)
  {
    g_last_sample_ms = now;

    Sample s{};
    s.t_s = now / 1000UL;
    if (g_has_uart_sample)
    {
      s.testBattery_s1 = (int16_t)lroundf(g_last_tb1);
      s.testBattery_s2 = (int16_t)lroundf(g_last_tb2);
      s.power_w = (int16_t)lroundf(g_last_power_w);
      s.auxCurrent_s1 = (int16_t)lroundf(g_last_aux);
      s.temperatures_s1 = (int16_t)lroundf(g_last_t1);
      s.temperatures_s2 = (int16_t)lroundf(g_last_t2);
    }

    dm_push(s);
  }

  while (Serial1.available())
  {
    char c = Serial1.read();
    if (c == '\r') continue;

    if (c == '\n')
    {
      g_uart_line[g_uart_len] = '\0';
      handle_uart_line(g_uart_line);
      g_uart_len = 0;
      continue;
    }

    if (g_uart_len < (UART_LINE_MAX - 1))
    {
      g_uart_line[g_uart_len++] = c;
    }
    else
    {
      // Line too long, reset buffer
      g_uart_len = 0;
    }
  }

  delay(5);
}
