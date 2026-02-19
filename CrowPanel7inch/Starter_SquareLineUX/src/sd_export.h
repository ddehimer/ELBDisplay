#pragma once
#include <lvgl.h>

bool sd_init();
bool sd_is_ready();

// Export all series from all key charts into one combined CSV file
bool sd_export_combined_csv(const char* name, const char* date,
                            lv_obj_t* battery_chart,
                            lv_obj_t* power_chart,
                            lv_obj_t* current_chart,
                            lv_obj_t* temperatures_chart);
