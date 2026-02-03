#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>
#include <lvgl.h>

#include "sd_export.h"


// DIS08070H microSD (TF) SPI pins (we'll verify/adjust if needed)
static constexpr int SD_CS   = 10;
static constexpr int SD_SCK  = 12;
static constexpr int SD_MISO = 13;
static constexpr int SD_MOSI = 11;

static SPIClass sdSPI(FSPI);

static void sanitize(char* s)
{
  for (int i = 0; s[i]; i++)
  {
    if (s[i] == ' ') s[i] = '_';
    bool ok = (s[i] >= '0' && s[i] <= '9') ||
              (s[i] >= 'A' && s[i] <= 'Z') ||
              (s[i] >= 'a' && s[i] <= 'z') ||
              s[i] == '_' || s[i] == '-' || s[i] == '.';
    if (!ok) s[i] = '_';
  }
}

bool sd_init()
{
  Serial.println("---- SD INIT (SPI) ----");
  Serial.printf("SPI pins: SCK=%d MISO=%d MOSI=%d CS=%d\n", SD_SCK, SD_MISO, SD_MOSI, SD_CS);

  sdSPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);

  if (!SD.begin(SD_CS, sdSPI, 20000000)) {
    Serial.println("❌ SD.begin failed");
    return false;
  }

  if (SD.cardType() == CARD_NONE) {
    Serial.println("❌ No SD card detected");
    return false;
  }

  Serial.println("✅ SD mounted");
  return true;
}

bool sd_export_csv(const char* name_raw, const char* date_raw)
{
  if (!name_raw || !date_raw) return false;

  char name[64];
  char date[32];
  snprintf(name, sizeof(name), "%s", name_raw);
  snprintf(date, sizeof(date), "%s", date_raw);

  sanitize(name);
  sanitize(date);

  char path[128];
  snprintf(path, sizeof(path), "/%s_%s.csv", date, name);

  Serial.print("Writing CSV: ");
  Serial.println(path);

  File f = SD.open(path, FILE_WRITE);
  if (!f) {
    Serial.println("❌ Failed to open file");
    return false;
  }

  f.println("time_s,vbat_v");
  for (int i = 0; i < 20; i++) {
    f.printf("%d,%.3f\n", i, 12.64);
  }

  f.close();
  Serial.println("✅ CSV export done");
  return true;
}

bool sd_export_chart_csv_first_series(const char* name_raw, const char* date_raw,
                                      const char* suffix,
                                      lv_obj_t* chart)
{
  if (!name_raw || !date_raw || !suffix || !chart) return false;

  // Get the first series on the chart (works even if SquareLine keeps it local)
  lv_chart_series_t* series = lv_chart_get_series_next(chart, NULL);
  if (!series) {
    Serial.println("❌ No chart series found on this chart.");
    return false;
  }

  // ---- same body as your old series export ----
  char name[64];
  char date[32];
  snprintf(name, sizeof(name), "%s", name_raw);
  snprintf(date, sizeof(date), "%s", date_raw);

  sanitize(name);
  sanitize(date);

  if (!SD.exists("/logs")) SD.mkdir("/logs");

  char suffix_buf[32];
  snprintf(suffix_buf, sizeof(suffix_buf), "%s", suffix);
  sanitize(suffix_buf);

  char path[160];
  snprintf(path, sizeof(path), "/logs/%s_%s_%s.csv", date, name, suffix_buf);

  Serial.print("Writing CSV: ");
  Serial.println(path);

  File f = SD.open(path, FILE_WRITE);
  if (!f) {
    Serial.println("❌ Failed to open file");
    return false;
  }

  f.println("index,y");

  uint16_t n = lv_chart_get_point_count(chart);
  const lv_coord_t* y = lv_chart_get_y_array(chart, series);

  for (uint16_t i = 0; i < n; i++) {
    if (y[i] == LV_CHART_POINT_NONE) continue;
    f.printf("%u,%d\n", i, (int)y[i]);
  }

  f.close();
  Serial.println("✅ Chart CSV export done");
  return true;
}


bool sd_export_chart_csv_all_series(const char* name_raw, const char* date_raw,
                                    const char* suffix,
                                    lv_obj_t* chart)
{
  if (!name_raw || !date_raw || !suffix || !chart) return false;

  char name[64];
  char date[32];
  snprintf(name, sizeof(name), "%s", name_raw);
  snprintf(date, sizeof(date), "%s", date_raw);

  sanitize(name);
  sanitize(date);

  if (!SD.exists("/logs")) SD.mkdir("/logs");

  char suffix_buf[32];
  snprintf(suffix_buf, sizeof(suffix_buf), "%s", suffix);
  sanitize(suffix_buf);

  uint16_t n = lv_chart_get_point_count(chart);
  lv_chart_series_t* series = NULL;
  uint16_t series_index = 0;
  bool found_any_series = false;
  bool all_ok = true;

  while ((series = lv_chart_get_series_next(chart, series)) != NULL) {
    found_any_series = true;

    char path[180];
    snprintf(path, sizeof(path), "/logs/%s_%s_%s_s%u.csv",
             date, name, suffix_buf, (unsigned)(series_index + 1U));

    Serial.print("Writing CSV: ");
    Serial.println(path);

    File f = SD.open(path, FILE_WRITE);
    if (!f) {
      Serial.println("Failed to open file");
      all_ok = false;
      series_index++;
      continue;
    }

    f.println("index,y");

    const lv_coord_t* y = lv_chart_get_y_array(chart, series);
    for (uint16_t i = 0; i < n; i++) {
      if (y[i] == LV_CHART_POINT_NONE) continue;
      f.printf("%u,%d\n", i, (int)y[i]);
    }

    f.close();
    series_index++;
  }

  if (!found_any_series) {
    Serial.println("No chart series found on this chart.");
    return false;
  }

  if (all_ok) Serial.println("Chart all-series CSV export done");
  return all_ok;
}

bool sd_export_all_graphs_combined_csv(const char* name_raw, const char* date_raw,
                                       lv_obj_t* battery_chart,
                                       lv_obj_t* shunt_chart,
                                       lv_obj_t* current_chart,
                                       lv_obj_t* temperatures_chart)
{
  static constexpr uint32_t SAMPLE_PERIOD_SECONDS = 60;

  if (!name_raw || !date_raw) return false;

  char name[64];
  char date[32];
  snprintf(name, sizeof(name), "%s", name_raw);
  snprintf(date, sizeof(date), "%s", date_raw);
  sanitize(name);
  sanitize(date);

  if (!SD.exists("/logs")) SD.mkdir("/logs");

  char path[180];
  snprintf(path, sizeof(path), "/logs/%s_%s_all_graphs.csv", date, name);

  if (SD.exists(path)) SD.remove(path);

  File f = SD.open(path, FILE_WRITE);
  if (!f) {
    Serial.println("Failed to open combined CSV file");
    return false;
  }

  struct ChartInfo {
    const char* label;
    lv_obj_t* chart;
  };

  ChartInfo charts[] = {
    {"TestBattery", battery_chart},
    {"Shunt", shunt_chart},
    {"AuxCurrent", current_chart},
    {"Temp", temperatures_chart},
  };

  struct SeriesCol {
    char label[40];
    const lv_coord_t* y;
    uint16_t point_count;
  };

  static constexpr uint16_t MAX_COLS = 16;
  SeriesCol cols[MAX_COLS];
  uint16_t col_count = 0;
  uint16_t max_points = 0;

  for (uint16_t c = 0; c < (uint16_t)(sizeof(charts) / sizeof(charts[0])); c++) {
    lv_obj_t* chart = charts[c].chart;
    if (!chart) continue;

    uint16_t n = lv_chart_get_point_count(chart);
    if (n > max_points) max_points = n;

    lv_chart_series_t* series = NULL;
    uint16_t series_idx = 0;

    while ((series = lv_chart_get_series_next(chart, series)) != NULL) {
      if (col_count >= MAX_COLS) break;

      snprintf(cols[col_count].label, sizeof(cols[col_count].label),
               "%s_s%u", charts[c].label, (unsigned)(series_idx + 1U));
      cols[col_count].y = lv_chart_get_y_array(chart, series);
      cols[col_count].point_count = n;

      col_count++;
      series_idx++;
    }
  }

  if (col_count == 0 || max_points == 0) {
    f.close();
    Serial.println("No chart data found for combined CSV export");
    return false;
  }

  f.print("index,t_s");
  for (uint16_t i = 0; i < col_count; i++) {
    f.print(",");
    f.print(cols[i].label);
  }
  f.println();

  for (uint16_t row = 0; row < max_points; row++) {
    f.print((unsigned)row);
    f.print(",");
    f.print((unsigned long)(row * SAMPLE_PERIOD_SECONDS));

    for (uint16_t col = 0; col < col_count; col++) {
      f.print(",");

      if (!cols[col].y) continue;
      if (row >= cols[col].point_count) continue;
      if (cols[col].y[row] == LV_CHART_POINT_NONE) continue;

      f.print((int)cols[col].y[row]);
    }

    f.println();
  }

  f.close();
  Serial.print("Combined CSV written: ");
  Serial.println(path);
  return true;
}
