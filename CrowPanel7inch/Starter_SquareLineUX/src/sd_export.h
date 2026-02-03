#pragma once
#include <lvgl.h>

bool sd_init();

// keep if you want
bool sd_export_csv(const char* name, const char* date);

// Export FIRST series of a chart to CSV (SquareLine-safe)
bool sd_export_chart_csv_first_series(const char* name, const char* date,
                                      const char* suffix,
                                      lv_obj_t* chart);

// Export EVERY series of a chart to its own CSV
bool sd_export_chart_csv_all_series(const char* name, const char* date,
                                    const char* suffix,
                                    lv_obj_t* chart);

// Export all series from all key charts into one combined CSV file
bool sd_export_all_graphs_combined_csv(const char* name, const char* date,
                                       lv_obj_t* battery_chart,
                                       lv_obj_t* shunt_chart,
                                       lv_obj_t* current_chart,
                                       lv_obj_t* temperatures_chart);
