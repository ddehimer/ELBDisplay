#pragma once
#include <lvgl.h>

bool sd_init();

// keep if you want
bool sd_export_csv(const char* name, const char* date);

// Export FIRST series of a chart to CSV (SquareLine-safe)
bool sd_export_chart_csv_first_series(const char* name, const char* date,
                                      const char* suffix,
                                      lv_obj_t* chart);
