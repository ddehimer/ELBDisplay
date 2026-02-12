#include <PCA9557.h>
#include <lvgl.h>
#include <Crowbits_DHT20.h>

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <stdio.h>
#include <stdarg.h>

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

// Latest UART data (RP2040) for ring buffer sampling
static bool g_has_uart_sample = false;
static int16_t g_last_tb1 = 0;
static int16_t g_last_tb2 = 0;
static int16_t g_last_shunt = 0;
static int16_t g_last_aux = 0;
static int16_t g_last_t1 = 0;
static int16_t g_last_t2 = 0;

// ----------------------------------------------------
// UART data parser (RP2040 -> ESP32)
// Expected line: DATA,<tb1>,<tb2>,<shunt>,<aux>,<t1>,<t2>\n
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

static void chart_push_value(lv_obj_t* chart, uint16_t series_idx, int16_t v)
{
  lv_chart_series_t* series = chart_series_by_index(chart, series_idx);
  if (!series) return;
  lv_chart_set_next_value(chart, series, v);
}

static bool parse_data_line(const char* line,
                            int16_t& tb1, int16_t& tb2, int16_t& shunt,
                            int16_t& aux, int16_t& t1, int16_t& t2)
{
  if (!line) return false;
  if (strncmp(line, "DATA,", 5) != 0) return false;

  int v1, v2, v3, v4, v5, v6;
  if (sscanf(line + 5, "%d,%d,%d,%d,%d,%d", &v1, &v2, &v3, &v4, &v5, &v6) != 6)
    return false;

  tb1 = (int16_t)v1;
  tb2 = (int16_t)v2;
  shunt = (int16_t)v3;
  aux = (int16_t)v4;
  t1 = (int16_t)v5;
  t2 = (int16_t)v6;
  return true;
}

static void handle_uart_line(const char* line)
{
  int16_t tb1, tb2, shunt, aux, t1, t2;
  if (!parse_data_line(line, tb1, tb2, shunt, aux, t1, t2)) return;

  // Update latest UART sample for ring buffer
  g_last_tb1 = tb1;
  g_last_tb2 = tb2;
  g_last_shunt = shunt;
  g_last_aux = aux;
  g_last_t1 = t1;
  g_last_t2 = t2;
  g_has_uart_sample = true;

  chart_push_value(ui_Chart2, 0, tb1);
  chart_push_value(ui_Chart2, 1, tb2);
  chart_push_value(ui_Chart6, 0, shunt);
  chart_push_value(ui_Chart1, 0, aux);
  chart_push_value(ui_Chart3, 0, t1);
  chart_push_value(ui_Chart3, 1, t2);

  lv_chart_refresh(ui_Chart2);
  lv_chart_refresh(ui_Chart6);
  lv_chart_refresh(ui_Chart1);
  lv_chart_refresh(ui_Chart3);
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

static int16_t chart_latest_value(lv_obj_t* chart, uint16_t series_idx)
{
  lv_chart_series_t* series = chart_series_by_index(chart, series_idx);
  if (!series) return 0;

  uint16_t n = lv_chart_get_point_count(chart);
  if (n == 0) return 0;

  const lv_coord_t* y = lv_chart_get_y_array(chart, series);
  if (!y) return 0;

  for (int i = (int)n - 1; i >= 0; --i) {
    if (y[i] != LV_CHART_POINT_NONE) return (int16_t)y[i];
  }
  return 0;
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
      s.testBattery_s1 = g_last_tb1;
      s.testBattery_s2 = g_last_tb2;
      s.shunt_s1 = g_last_shunt;
      s.auxCurrent_s1 = g_last_aux;
      s.temperatures_s1 = g_last_t1;
      s.temperatures_s2 = g_last_t2;
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

