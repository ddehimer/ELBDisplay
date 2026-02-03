class CurrentController:
    def __init__(self, adc, dac):
        self.adc = adc
        self.dac = dac
        self.start_mode = False

    def update(self):
        if self.start_mode:
            counts = self.adc.read_channel(1)
            volts = self.adc.counts_to_volts(counts)

            # Direct mapping: POT → DAC
            code = int((volts / 5.0) * 4095)
            self.dac.set_raw(code)
        else:
            self.dac.set_raw(0)
