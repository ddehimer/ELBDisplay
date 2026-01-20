import sys
import time
import random
import math
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
        self.shunt_voltage_nominal = 0.020   # V (20 mV nominal)
        self.aux_battery_current_nominal = 1.50  # A nominal


        self.pre_driver_voltage = 5.10
        self.driver_voltage = 10.02
        self.power_stage_voltage = 12.58   
        self.vset_pot = 1.65        


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
        self.x_data = deque(maxlen=2000)  # minutes (shared x for all plots)
        self.y_data = deque(maxlen=2000)  # test batt volts
        self.shunt_y = deque(maxlen=2000)  # shunt volts
        self.aux_i_y = deque(maxlen=2000)  # aux current amps


        # Smoothed y-axis bounds
        # Smoothed y-axis bounds (separate per plot)
        self.batt_ymin = None
        self.batt_ymax = None

        self.shunt_ymin = None
        self.shunt_ymax = None

        self.auxi_ymin = None
        self.auxi_ymax = None


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
        # -------- Tab 1: Battery + Shunt + Aux Current Graphs --------
    def build_battery_tab(self) -> QWidget:
        tab = QWidget()

        root = QVBoxLayout(tab)

        # ---- Top numeric title (optional, keep it simple) ----
        title = QLabel("Live Monitoring")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        # ---- Row of two plots (side-by-side) ----
        top_row = QHBoxLayout()

        pg.setConfigOptions(antialias=True)

        # --- Plot 1: Test Battery Voltage ---
        left_col = QVBoxLayout()
        batt_label = QLabel("Test Battery Voltage")
        batt_label.setAlignment(Qt.AlignCenter)
        batt_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.batt_value_label = QLabel(f"{self.test_battery_voltage_start:.2f} V")
        self.batt_value_label.setAlignment(Qt.AlignCenter)
        self.batt_value_label.setStyleSheet("font-size: 28px;")

        self.plot_batt = pg.PlotWidget()
        self.plot_batt.setLabel("left", "Voltage", units="V")
        self.plot_batt.setLabel("bottom", "Time", units="minutes")
        self.plot_batt.setTitle("Battery Voltage vs Time")
        self.plot_batt.showGrid(x=True, y=True)
        self.plot_batt.setXRange(0, self.max_minutes, padding=0)

        self.curve_batt = self.plot_batt.plot([], [], pen=pg.mkPen(width=2))

        left_col.addWidget(batt_label)
        left_col.addWidget(self.batt_value_label)
        left_col.addWidget(self.plot_batt, stretch=1)

        # --- Plot 2: Shunt Voltage ---
        right_col = QVBoxLayout()
        shunt_label = QLabel("Shunt Voltage")
        shunt_label.setAlignment(Qt.AlignCenter)
        shunt_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.shunt_value_label = QLabel(f"{self.shunt_voltage_nominal*1000:.1f} mV")
        self.shunt_value_label.setAlignment(Qt.AlignCenter)
        self.shunt_value_label.setStyleSheet("font-size: 28px;")

        self.plot_shunt = pg.PlotWidget()
        self.plot_shunt.setLabel("left", "Shunt", units="V")
        self.plot_shunt.setLabel("bottom", "Time", units="minutes")
        self.plot_shunt.setTitle("Shunt Voltage vs Time")
        self.plot_shunt.showGrid(x=True, y=True)
        self.plot_shunt.setXRange(0, self.max_minutes, padding=0)

        self.curve_shunt = self.plot_shunt.plot([], [], pen=pg.mkPen(width=2))

        right_col.addWidget(shunt_label)
        right_col.addWidget(self.shunt_value_label)
        right_col.addWidget(self.plot_shunt, stretch=1)

        top_row.addLayout(left_col, stretch=1)
        top_row.addLayout(right_col, stretch=1)

        root.addLayout(top_row, stretch=2)

        # ---- Bottom plot (full width): Aux battery current ----
        bottom_col = QVBoxLayout()

        aux_label = QLabel("Aux Battery Current")
        aux_label.setAlignment(Qt.AlignCenter)
        aux_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.aux_value_label = QLabel(f"{self.aux_battery_current_nominal:.2f} A")
        self.aux_value_label.setAlignment(Qt.AlignCenter)
        self.aux_value_label.setStyleSheet("font-size: 28px;")

        self.plot_auxi = pg.PlotWidget()
        self.plot_auxi.setLabel("left", "Current", units="A")
        self.plot_auxi.setLabel("bottom", "Time", units="minutes")
        self.plot_auxi.setTitle("Aux Battery Current vs Time")
        self.plot_auxi.showGrid(x=True, y=True)
        self.plot_auxi.setXRange(0, self.max_minutes, padding=0)

        self.curve_auxi = self.plot_auxi.plot([], [], pen=pg.mkPen(width=2))

        bottom_col.addWidget(aux_label)
        bottom_col.addWidget(self.aux_value_label)
        bottom_col.addWidget(self.plot_auxi, stretch=1)

        root.addLayout(bottom_col, stretch=1)

        return tab


    # -------- Tab 2: Pre/Driver/Power Voltages --------
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

        layout.addWidget(QLabel("Vset (POT):"), 4, 0)
        layout.addWidget(QLabel(f"{self.vset_pot:.2f} V"), 4, 1)

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
        real_elapsed = time.time() - self.start_time
        simulated_minutes = real_elapsed * self.time_scale

        if simulated_minutes > self.max_minutes:
            self.timer.stop()
            return

        # ---- Battery discharge model (same idea as before) ----
        V_start = self.test_battery_voltage_start
        V_end = self.test_battery_voltage_end

        slope = (V_start - V_end) / self.max_minutes
        curvature = 0.0008

        batt_v = V_start - slope * simulated_minutes - curvature * (simulated_minutes ** 2)

        # ---- Shunt voltage (random-ish ripple + slight trend) ----
        # Nominal around 20 mV with a little sine ripple + gaussian noise
        shunt_base = self.shunt_voltage_nominal
        ripple = 0.003 * math.sin(2 * math.pi * simulated_minutes / 6.0)  # ~6-min ripple
        noise = random.gauss(0.0, 0.0006)  # 0.6 mV noise
        shunt_v = max(0.0, shunt_base + ripple + noise)

        # ---- Aux battery current (random-ish) ----
        aux_base = self.aux_battery_current_nominal
        aux_ripple = 0.25 * math.sin(2 * math.pi * simulated_minutes / 10.0)  # slow ripple
        aux_noise = random.gauss(0.0, 0.05)  # noise in amps
        aux_i = max(0.0, aux_base + aux_ripple + aux_noise)

        # Update numeric displays
        self.batt_value_label.setText(f"{batt_v:.2f} V")
        self.shunt_value_label.setText(f"{shunt_v*1000:.1f} mV")
        self.aux_value_label.setText(f"{aux_i:.2f} A")

        # Store X + Y data
        self.x_data.append(simulated_minutes)
        self.y_data.append(batt_v)
        self.shunt_y.append(shunt_v)
        self.aux_i_y.append(aux_i)

        # Update plot lines
        x = list(self.x_data)
        self.curve_batt.setData(x, list(self.y_data))
        self.curve_shunt.setData(x, list(self.shunt_y))
        self.curve_auxi.setData(x, list(self.aux_i_y))

        # Helper for smoothed Y range
        def smooth_y_range(y_vals, ymin, ymax, plot, pad_frac=0.15, alpha=0.15):
            if len(y_vals) < 2:
                return ymin, ymax

            y_min = min(y_vals)
            y_max = max(y_vals)
            base_range = (y_max - y_min) if (y_max != y_min) else 1.0
            padding = pad_frac * base_range

            target_min = y_min - padding
            target_max = y_max + padding

            if ymin is None or ymax is None:
                ymin = target_min
                ymax = target_max
            else:
                ymin += alpha * (target_min - ymin)
                ymax += alpha * (target_max - ymax)

            plot.setYRange(ymin, ymax, padding=0)
            return ymin, ymax

        # Apply smoothed autoscaling to each plot independently
        self.batt_ymin, self.batt_ymax = smooth_y_range(self.y_data, self.batt_ymin, self.batt_ymax, self.plot_batt)
        self.shunt_ymin, self.shunt_ymax = smooth_y_range(self.shunt_y, self.shunt_ymin, self.shunt_ymax, self.plot_shunt)
        self.auxi_ymin, self.auxi_ymax = smooth_y_range(self.aux_i_y, self.auxi_ymin, self.auxi_ymax, self.plot_auxi)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
