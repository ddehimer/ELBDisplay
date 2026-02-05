#pragma once
#include <stddef.h>
#include <stdint.h>

struct Sample {
  uint32_t t_s;
  int16_t testBattery_s1;
  int16_t testBattery_s2;
  int16_t shunt_s1;
  int16_t auxCurrent_s1;
  int16_t temperatures_s1;
  int16_t temperatures_s2;
};

void dm_init();
void dm_push(const Sample& s);
size_t dm_size();
size_t dm_capacity();
bool dm_get_oldest(size_t index, Sample& out);
