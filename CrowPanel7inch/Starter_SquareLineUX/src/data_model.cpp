#include "data_model.h"

static constexpr size_t DM_CAP = 256;
static Sample g_buf[DM_CAP];
static size_t g_write_index = 0;   // next write index
static size_t g_count = 0;  // number of valid samples

void dm_init() {
  g_write_index = 0;
  g_count = 0;
}

void dm_push(const Sample& s) {
  g_buf[g_write_index] = s;
  g_write_index = (g_write_index + 1) % DM_CAP;
  if (g_count < DM_CAP) g_count++;
}

size_t dm_size() { return g_count; }
size_t dm_capacity() { return DM_CAP; }

bool dm_get_oldest(size_t index, Sample& out) {
  if (index >= g_count) return false;
  size_t oldest = (g_write_index + DM_CAP - g_count) % DM_CAP;
  size_t pos = (oldest + index) % DM_CAP;
  out = g_buf[pos];
  return true;
}
