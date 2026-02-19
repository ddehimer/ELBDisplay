#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>
#include <lvgl.h>

#include "sd_export.h"
#include "data_model.h"


// DIS08070H microSD (TF) SPI pins (we'll verify/adjust if needed)
static constexpr int SD_CS   = 10;
static constexpr int SD_SCK  = 12;
static constexpr int SD_MISO = 13;
static constexpr int SD_MOSI = 11;

static SPIClass sdSPI(FSPI);

static bool sd_try_mount(bool log)
{
  sdSPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);

  if (!SD.begin(SD_CS, sdSPI, 20000000)) {
    if (log) Serial.println("SD.begin failed");
    return false;
  }

  if (SD.cardType() == CARD_NONE) {
    if (log) Serial.println("No SD card detected");
    return false;
  }

  return true;
}

// Replace any invalid characters with underscores for name and date of CSV export
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
  // print SPI pin mapping to serial monitor
  Serial.println("---- SD INIT (SPI) ----");
  Serial.printf("SPI pins: SCK=%d MISO=%d MOSI=%d CS=%d\n", SD_SCK, SD_MISO, SD_MOSI, SD_CS);

  if (!sd_try_mount(true)) return false;

  // if SD card is present and accessible, serial monitor gives green check
  Serial.println("SD mounted");
  return true;
}

bool sd_is_ready()
{
  if (SD.cardType() != CARD_NONE) {
    File root = SD.open("/");
    if (root) {
      root.close();
      return true;
    }
  }

  if (!sd_try_mount(false)) return false;

  File root = SD.open("/");
  if (!root) return false;
  root.close();
  return true;
}

bool sd_export_combined_csv(const char* name_raw, const char* date_raw,
                            lv_obj_t* battery_chart,
                            lv_obj_t* power_chart,
                            lv_obj_t* current_chart,
                            lv_obj_t* temperatures_chart)
{
  (void)battery_chart;
  (void)power_chart;
  (void)current_chart;
  (void)temperatures_chart;

  // if name or date are null fail immediately
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

  const size_t count = dm_size();
  if (count == 0) {
    f.close();
    Serial.println("No buffered data found for combined CSV export");
    return false;
  }

  f.println("index,t_s,TestBattery_V,TestBattery_A,Power_W,AuxCurrent_s1,Temp_s1,Temp_s2");

  for (size_t i = 0; i < count; i++) {
    Sample s{};
    if (!dm_get_oldest(i, s)) continue;

    f.printf("%u,%lu,%d,%d,%d,%d,%d,%d\n",
             (unsigned)i,
             (unsigned long)s.t_s,
             (int)s.testBattery_s1,
             (int)s.testBattery_s2,
             (int)s.power_w,
             (int)s.auxCurrent_s1,
             (int)s.temperatures_s1,
             (int)s.temperatures_s2);
  }

  f.close();
  Serial.print("Combined CSV written: ");
  Serial.println(path);
  return true;
}
