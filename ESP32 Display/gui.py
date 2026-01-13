import sys
import time
from collections import deque

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QTabWidget,
    QGridLayout,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QHBoxLayout,
)

import pyqtgraph as pg


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ELB Display")
        self.resize(900, 600)

        # -------------------------
        # Demo / mock values
        # -------------------------
        self.test_battery_voltage_start = 12.64
        self.test_battery_voltage_end = 11.80

        self.pre_driver_voltage = 5.10
        self.driver_voltage = 10.02
        self.power_stage_voltage = 12.58

        self.test_battery_temp = 27.8
        self.heatsink_temp = 41.3

        # -------------------------
        # Plot configuration
        # -------------------------
        self.max_minutes = 60

        # Time scaling: 10 real seconds == 60 simulated minutes
        self.demo_seconds = 10
        self.time_scale = self.max_minutes / self.demo_seconds  # 6 simulated min / real sec

        self.start_time = time.time()

        # Plot buffers
        self.x_data = deque(maxlen=2000)  # minutes
        self.y_data = deque(maxlen=2000)  # volts

        # Smoothed y-axis bounds
        self.y_axis_min = None
        self.y_axis_max = None

        # -------------------------
        # Tabs
        # -------------------------
        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        tabs.addTab(self.build_battery_tab(), "Battery")
        tabs.addTab(self.build_voltage_tab(), "Voltages")
        tabs.addTab(self.build_temp_tab(), "Temperatures")
        tabs.addTab(self.build_storage_tab(), "File Storage")

        # -------------------------
        # Timer update (fast for demo)
        # -------------------------
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)  # 20 Hz so the 10-second demo looks smooth

    # -------- Tab 1: Battery Voltage + Graph --------
    def build_battery_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        title = QLabel("Test Battery Voltage")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        self.batt_value_label = QLabel(f"{self.test_battery_voltage_start:.2f} V")
        self.batt_value_label.setAlignment(Qt.AlignCenter)
        self.batt_value_label.setStyleSheet("font-size: 36px;")

        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("left", "Voltage", units="V")
        self.plot.setLabel("bottom", "Time", units="minutes")
        self.plot.setTitle("Battery Voltage vs Time")
        self.plot.showGrid(x=True, y=True)

        # Lock X-axis to 0..60 minutes (even though we simulate it in 10 seconds)
        self.plot.setXRange(0, self.max_minutes, padding=0)

        self.curve = self.plot.plot([], [], pen=pg.mkPen(width=2))

        layout.addWidget(title)
        layout.addWidget(self.batt_value_label)
        layout.addWidget(self.plot, stretch=1)

        return tab

    # -------- Tab 2: Pre/Driver/Power Voltages --------
    def build_voltage_tab(self) -> QWidget:
        tab = QWidget()
        layout = QGridLayout(tab)

        layout.addWidget(QLabel("Pre-Driver Voltage:"), 0, 0)
        layout.addWidget(QLabel(f"{self.pre_driver_voltage:.2f} V"), 0, 1)

        layout.addWidget(QLabel("Driver Voltage:"), 1, 0)
        layout.addWidget(QLabel(f"{self.driver_voltage:.2f} V"), 1, 1)

        layout.addWidget(QLabel("Power Stage Voltage:"), 2, 0)
        layout.addWidget(QLabel(f"{self.power_stage_voltage:.2f} V"), 2, 1)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        return tab

    # -------- Tab 3: Temperatures --------
    def build_temp_tab(self) -> QWidget:
        tab = QWidget()
        layout = QGridLayout(tab)

        layout.addWidget(QLabel("Test Battery Temperature:"), 0, 0)
        layout.addWidget(QLabel(f"{self.test_battery_temp:.1f} °C"), 0, 1)

        layout.addWidget(QLabel("Heatsink Temperature:"), 1, 0)
        layout.addWidget(QLabel(f"{self.heatsink_temp:.1f} °C"), 1, 1)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        return tab

    # -------- Tab 4: File Storage / Export --------
    def build_storage_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        title = QLabel("File Storage")
        title.setAlignment(Qt.AlignLeft)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        info = QLabel(
            "Export the Battery Voltage vs Time data to a CSV file.\n"
            "Columns: time_minutes, voltage_V"
        )
        info.setStyleSheet("font-size: 12px;")

        button_row = QHBoxLayout()
        export_btn = QPushButton("Export CSV")
        export_btn.setMinimumHeight(40)
        export_btn.clicked.connect(self.export_csv)

        button_row.addWidget(export_btn)
        button_row.addStretch()

        self.export_status = QLabel("Status: ready")
        self.export_status.setStyleSheet("font-size: 12px;")

        layout.addWidget(title)
        layout.addWidget(info)
        layout.addLayout(button_row)
        layout.addWidget(self.export_status)
        layout.addStretch()

        return tab

    # -------- Export Function --------
    def export_csv(self):
        if len(self.x_data) < 2:
            QMessageBox.warning(self, "Export CSV", "Not enough data to export yet.")
            return

        default_name = f"elb_battery_log_{time.strftime('%Y%m%d_%H%M%S')}.csv"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV",
            default_name,
            "CSV Files (*.csv)"
        )

        if not path:
            return  # user cancelled

        try:
            with open(path, "w", newline="") as f:
                f.write("time_minutes,voltage_V\n")
                for t, v in zip(self.x_data, self.y_data):
                    f.write(f"{t:.6f},{v:.6f}\n")

            self.export_status.setText(f"Status: exported to {path}")
            QMessageBox.information(self, "Export CSV", "Export completed successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Export CSV", f"Export failed:\n{e}")
            self.export_status.setText("Status: export failed")

    # -------- Update loop --------
    def update_plot(self):
        # --- Real elapsed time (seconds) ---
        real_elapsed = time.time() - self.start_time

        # --- Convert to simulated minutes (0..60) compressed into demo_seconds ---
        simulated_minutes = real_elapsed * self.time_scale

        if simulated_minutes > self.max_minutes:
            self.timer.stop()
            return

        # ---- Discharge model over 60 minutes (curved) ----
        V_start = self.test_battery_voltage_start
        V_end = self.test_battery_voltage_end

        slope = (V_start - V_end) / self.max_minutes
        curvature = 0.0008  # tweak for shape

        voltage = V_start - slope * simulated_minutes - curvature * (simulated_minutes ** 2)

        # Update numeric display
        self.batt_value_label.setText(f"{voltage:.2f} V")

        # Store data
        self.x_data.append(simulated_minutes)
        self.y_data.append(voltage)

        # Update plot line
        self.curve.setData(list(self.x_data), list(self.y_data))

        # -------------------------
        # Dynamic Y-axis scaling (smoothed)
        # -------------------------
        if len(self.y_data) > 1:
            y_min = min(self.y_data)
            y_max = max(self.y_data)

            base_range = (y_max - y_min) if (y_max != y_min) else 1.0
            padding = 0.15 * base_range  # 15% padding

            target_min = y_min - padding
            target_max = y_max + padding

            if self.y_axis_min is None:
                self.y_axis_min = target_min
                self.y_axis_max = target_max
            else:
                alpha = 0.15
                self.y_axis_min += alpha * (target_min - self.y_axis_min)
                self.y_axis_max += alpha * (target_max - self.y_axis_max)

            self.plot.setYRange(self.y_axis_min, self.y_axis_max, padding=0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
