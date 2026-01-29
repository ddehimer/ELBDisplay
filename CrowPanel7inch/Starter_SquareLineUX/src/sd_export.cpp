#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>

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
