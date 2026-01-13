import sys
from PySide6.QtWidgets import QApplication, QLabel

battery_voltage = 12.64

app = QApplication(sys.argv)

label = QLabel(f"Test Battery Voltage: {battery_voltage:.2f} V")
label.setWindowTitle("ELB Display")
label.resize(320, 120)
label.show()

sys.exit(app.exec())
