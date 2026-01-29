class CurrentDAC:
    MCP4725_ADDR = 0x60

    def __init__(self, i2c, vref=5, divider_gain=0.049):
        self.i2c = i2c
        self.vref = vref
        self.divider_gain = divider_gain
        self.last_code = 0
        self.set_raw(0)

    def set_raw(self, code):
        code = max(0, min(4095, int(code)))
        cmd = 0x40
        msb = (code >> 4) & 0xFF
        lsb = (code & 0x0F) << 4
        self.i2c.writeto(self.MCP4725_ADDR, bytes([cmd, msb, lsb]))
        self.last_code = code

    def set_current_set_voltage(self, volts):
        max_v = self.vref * self.divider_gain
        volts = max(0.0, min(max_v, volts))
        dac_v = volts / self.divider_gain
        code = int((dac_v / self.vref) * 4095)
        self.set_raw(code)
