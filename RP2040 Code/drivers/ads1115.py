print("ADS1115 DRIVER LOADED v3")

import time

class ADS1115:
    REG_CONVERT = 0x00
    REG_CONFIG = 0x01

    def __init__(self, i2c, address=0x49):
        self.i2c = i2c
        self.address = address

    def read_channel(self, ch):
        if ch < 0 or ch > 3:
            raise ValueError("ADS1115 channel must be 0–3")

        mux = 0x4000 | (ch << 12)

        config = (
            0x8000 |   # Start single conversion
            mux |
            0x0000 |   # PGA ±6.144V
            0x0100 |   # 128 SPS
            0x0003     # Disable comparator
        )

        # Write config (NO keyword args)
        self.i2c.writeto_mem(
            self.address,
            self.REG_CONFIG,
            bytes([(config >> 8) & 0xFF, config & 0xFF])
        )

        # Conversion delay (NO keyword args)
        time.sleep_ms(9)

        data = self.i2c.readfrom_mem(self.address, self.REG_CONVERT, 2)
        return (data[0] << 8) | data[1]

    @staticmethod
    def counts_to_volts(counts):
        return counts * 6.144 / 32768
