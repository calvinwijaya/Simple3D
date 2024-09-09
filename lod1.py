import sys
import subprocess
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, 
                             QFileDialog, QTextEdit, QLabel, QHBoxLayout, QLineEdit, 
                             QWidget)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap

# pip install PyQt5

class ProcessThread(QThread):
    output_signal = pyqtSignal(str)

    def __init__(self, building_outline, point_cloud, dsm, dtm, epsg_code, output_dir):
        super().__init__()
        self.building_outline = building_outline
        self.point_cloud = point_cloud
        self.dsm = dsm
        self.dtm = dtm
        self.epsg_code = epsg_code
        self.output_dir = output_dir

    def run(self):
        # Run the process and capture output
        command = ['python', 'main.py', '--building_outline', self.building_outline, '--epsg', self.epsg_code, '--output', self.output_dir]
        
        if self.point_cloud:
            command.extend(['--point_cloud', self.point_cloud])
        if self.dsm and self.dtm:
            command.extend(['--dsm', self.dsm, '--dtm', self.dtm])
        
        # Run the process and capture output
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        
        # Capture stdout
        for line in process.stdout:
            self.output_signal.emit(line.strip())

        # Capture stderr (in case there are errors)
        for line in process.stderr:
            self.output_signal.emit(f"Error: {line.strip()}")

        process.stdout.close()
        process.stderr.close()
        process.wait()

class CityModelGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        # Main layout
        layout = QVBoxLayout()

        # Load Building Outline input (GeoJSON or SHP)
        self.geojson_label = QLabel('Load Building Outline (GeoJSON or SHP):')
        self.geojson_path = QLineEdit(self)
        self.geojson_path.setReadOnly(True)
        self.geojson_btn = QPushButton('...', self)
        self.geojson_btn.clicked.connect(self.select_geojson_or_shp)

        # Layout for GeoJSON/SHP
        geojson_layout = QHBoxLayout()
        geojson_layout.addWidget(self.geojson_path)
        geojson_layout.addWidget(self.geojson_btn)

        # Load Point Cloud input (LAS)
        self.las_label = QLabel('Load Point Cloud (LAS):')
        self.las_path = QLineEdit(self)
        self.las_path.setReadOnly(True)
        self.las_btn = QPushButton('...', self)
        self.las_btn.clicked.connect(self.select_las)

        # Layout for LAS
        las_layout = QHBoxLayout()
        las_layout.addWidget(self.las_path)
        las_layout.addWidget(self.las_btn)

         # DSM input
        self.dsm_label = QLabel('Load DSM (TIF):')
        self.dsm_path = QLineEdit(self)
        self.dsm_path.setReadOnly(True)
        self.dsm_btn = QPushButton('...', self)
        self.dsm_btn.clicked.connect(self.select_dsm)
        dsm_layout = QHBoxLayout()
        dsm_layout.addWidget(self.dsm_path)
        dsm_layout.addWidget(self.dsm_btn)

        # DTM input
        self.dtm_label = QLabel('Load DTM (TIF):')
        self.dtm_path = QLineEdit(self)
        self.dtm_path.setReadOnly(True)
        self.dtm_btn = QPushButton('...', self)
        self.dtm_btn.clicked.connect(self.select_dtm)
        dtm_layout = QHBoxLayout()
        dtm_layout.addWidget(self.dtm_path)
        dtm_layout.addWidget(self.dtm_btn)

        # EPSG Code input
        self.epsg_label = QLabel('Enter EPSG Code:')
        self.epsg_code = QLineEdit(self)

        # Output Directory input
        self.output_label = QLabel('Select Output Directory:')
        self.output_path = QLineEdit(self)
        self.output_path.setReadOnly(True)
        self.output_btn = QPushButton('...', self)
        self.output_btn.clicked.connect(self.select_output_directory)

        # Layout for Output Directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.output_btn)

        # Buttons (Start and Replay)
        buttons_layout = QHBoxLayout()

        # Start Button
        self.start_btn = QPushButton('Start', self)
        self.start_btn.setMinimumWidth(150)
        self.start_btn.clicked.connect(self.start_process)

        # Replay Button (Clear input fields)
        self.replay_btn = QPushButton(self)
        self.replay_btn.setIcon(QIcon("ui/replay.png"))  # Add your replay icon image here
        self.replay_btn.setFixedWidth(100)
        self.replay_btn.clicked.connect(self.clear_inputs)

        # Add Start and Replay buttons to layout
        buttons_layout.addWidget(self.start_btn)
        buttons_layout.addWidget(self.replay_btn)

        # Console log
        self.log_console = QTextEdit(self)
        self.log_console.setReadOnly(True)

        # Add widgets to layout
        layout.addWidget(self.geojson_label)
        layout.addLayout(geojson_layout)
        layout.addWidget(self.las_label)
        layout.addLayout(las_layout)
        layout.addWidget(self.dsm_label)
        layout.addLayout(dsm_layout)
        layout.addWidget(self.dtm_label)
        layout.addLayout(dtm_layout)
        layout.addWidget(self.epsg_label)
        layout.addWidget(self.epsg_code)
        layout.addWidget(self.output_label)
        layout.addLayout(output_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(QLabel('Console Log:'))
        layout.addWidget(self.log_console)

        # Watermark Layout
        watermark_layout = QHBoxLayout()
        watermark_logo = QLabel(self)
        watermark_logo.setPixmap(QPixmap("ui/ugm.png").scaled(40, 40))
        watermark_layout.addWidget(watermark_logo)
        watermark_text = QLabel("Department of Geodetic Engineering\nFaculty of Engineering Universitas Gadjah Mada")
        watermark_layout.addWidget(watermark_text)
        watermark_layout.addStretch(1)
        watermark_layout.setContentsMargins(0, 20, 0, 0)
        layout.addLayout(watermark_layout)

        # Set layout for main window
        self.setLayout(layout)
        self.setWindowTitle('LOD1 3D City Model - CityJSON Generator')
        self.setGeometry(100, 100, 800, 800)

        # Set the window icon
        self.setWindowIcon(QIcon("ui/logo.png"))  # Replace with the path to your logo image

    # Functions for selecting files/directories
    def select_geojson_or_shp(self):
        geojson_shp_file, _ = QFileDialog.getOpenFileName(self, "Select Building Outline (GeoJSON or SHP)", "", "GeoJSON/Shapefile Files (*.geojson *.shp)")
        if geojson_shp_file:
            self.geojson_path.setText(geojson_shp_file)
            self.log_console.append(f"Selected Building Outline: {geojson_shp_file}")

    def select_las(self):
        las_file, _ = QFileDialog.getOpenFileName(self, "Select Point Cloud (LAS)", "", "LAS Files (*.las)")
        if las_file:
            self.las_path.setText(las_file)
            self.log_console.append(f"Selected Point Cloud: {las_file}")

    def select_dsm(self):
        dsm_file, _ = QFileDialog.getOpenFileName(self, "Select DSM (TIF)", "", "TIF Files (*.tif)")
        if dsm_file:
            self.dsm_path.setText(dsm_file)
            self.log_console.append(f"Selected DSM: {dsm_file}")

    def select_dtm(self):
        dtm_file, _ = QFileDialog.getOpenFileName(self, "Select DTM (TIF)", "", "TIF Files (*.tif)")
        if dtm_file:
            self.dtm_path.setText(dtm_file)
            self.log_console.append(f"Selected DTM: {dtm_file}")

    def select_output_directory(self):
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if output_dir:
            self.output_path.setText(output_dir)
            self.log_console.append(f"Selected Output Directory: {output_dir}")

    def start_process(self):
        # Gather inputs
        building_outline = self.geojson_path.text()
        point_cloud = self.las_path.text()
        dsm = self.dsm_path.text()
        dtm = self.dtm_path.text()
        epsg_code = self.epsg_code.text()
        output_dir = self.output_path.text()

        if not (point_cloud or (dsm and dtm)):
            self.log_console.append("Error: Please provide either a point cloud or both DSM and DTM.")
            return

        # Start the process in a separate thread
        self.process_thread = ProcessThread(building_outline, point_cloud, dsm, dtm, epsg_code, output_dir)
        self.process_thread.output_signal.connect(self.update_console_log)
        self.process_thread.start()

    def update_console_log(self, message):
        self.log_console.append(message)

    def clear_inputs(self):
        # Clear all the input fields
        self.geojson_path.clear()
        self.las_path.clear()
        self.dsm_path.clear()
        self.dtm_path.clear()
        self.epsg_code.clear()
        self.output_path.clear()
        self.log_console.clear()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = CityModelGUI()
    ex.show()
    sys.exit(app.exec_())