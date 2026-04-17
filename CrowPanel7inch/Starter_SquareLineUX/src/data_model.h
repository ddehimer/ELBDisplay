#pragma once
#include <stddef.h>
#include <stdint.h>

struct Sample {
  uint32_t t_s;
  int32_t testBattery_mv;
  int32_t testBattery_ma;
  int32_t power_mw;
  int32_t energy_wh_milli;
  int32_t auxCurrent_ma;
  int32_t heatsinkTemp_mc;
  int32_t batteryTemp_mc;
};

void dm_init();
void dm_push(const Sample& s);
size_t dm_size();
size_t dm_capacity();
bool dm_get_oldest(size_t index, Sample& out);
