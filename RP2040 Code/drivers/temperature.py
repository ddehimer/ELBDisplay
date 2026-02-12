import time
import math

class HeatsinkTemp:
    REG_CONVERSION = 0x00
    REG_CONFIG     = 0x01

    def __init__(
        self,
        i2c,
        ads_addr=0x4A,
        r_fixed=4990.0,
        v_supply=5,
        r0=12000.0,
        t0=298.15,
        beta=3950.0
    ):
        self.i2c = i2c
        self.addr = ads_addr

        # Hardware constants
        self.R_FIXED = r_fixed
        self.V_SUPPLY = v_supply

        # Thermistor constants
        self.R0 = r0
        self.T0 = t0
        self.BETA = beta

        # AIN0, ±6.144V, single-shot, 128 SPS
        self.CONFIG_AIN0 = 0xD183

    def _read_vadc(self):
        self.i2c.writeto_mem(
            self.addr,
            self.REG_CONFIG,
            bytes([
                (self.CONFIG_AIN0 >> 8) & 0xFF,
                self.CONFIG_AIN0 & 0xFF
            ])
        )

        time.sleep_ms(10)

        data = self.i2c.readfrom_mem(self.addr, self.REG_CONVERSION, 2)
        raw = (data[0] << 8) | data[1]

        if raw & 0x8000:
            raw -= 65536

        return raw * 6.144 / 32768

    def read(self):
        v = self._read_vadc()

        if v <= 0.01 or v >= (self.V_SUPPLY - 0.01):
            return None, None, v

        r_ntc = self.R_FIXED * (self.V_SUPPLY - v) / v

        temp_k = 1.0 / (
            (1.0 / self.T0) +
            (1.0 / self.BETA) * math.log(r_ntc / self.R0)
        )

        temp_c = temp_k - 273.15
        return temp_c, r_ntc, v
