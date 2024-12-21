import sys
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QFileDialog, QMessageBox, QHBoxLayout, QTextEdit
from PyQt5.QtGui import QIcon, QPixmap
import geopandas as gpd
from sqlalchemy import create_engine
from simplekml import Kml, AltitudeMode
from shapely.geometry import Polygon

class KMLGeneratorApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Create labels and input fields
        self.user_label = QLabel('Username:')
        self.user_input = QLineEdit()

        self.password_label = QLabel('Password:')
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        self.host_label = QLabel('Host:')
        self.host_input = QLineEdit('localhost')

        self.port_label = QLabel('Port:')
        self.port_input = QLineEdit('5432')

        self.database_label = QLabel('Database:')
        self.database_input = QLineEdit()

        self.table_label = QLabel('Table:')
        self.table_input = QLineEdit()

        # File path selection button
        file_layout = QHBoxLayout()
        self.file_label = QLabel('Save KML File Path:')
        self.file_input = QLineEdit(self)
        self.file_input.setReadOnly(True)
        self.file_button = QPushButton('...', self)
        self.file_button.clicked.connect(self.browse_file)

        file_layout.addWidget(self.file_input)
        file_layout.addWidget(self.file_button)

        # Generate button
        self.generate_button = QPushButton('Generate KML')
        self.generate_button.clicked.connect(self.generate_kml)

        # Console log
        self.console_log = QTextEdit()
        self.console_log.setReadOnly(True)
        self.console_log.setPlaceholderText("Console log...")
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.user_label)
        layout.addWidget(self.user_input)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.host_label)
        layout.addWidget(self.host_input)
        layout.addWidget(self.port_label)
        layout.addWidget(self.port_input)
        layout.addWidget(self.database_label)
        layout.addWidget(self.database_input)
        layout.addWidget(self.table_label)
        layout.addWidget(self.table_input)
        layout.addWidget(self.file_label)
        layout.addLayout(file_layout)  # Add the entire file layout
        layout.addWidget(self.generate_button)
        layout.addWidget(self.console_log)

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

        self.setLayout(layout)
        self.setWindowTitle('KML Generator')
        self.setGeometry(100, 100, 800, 600)

    def browse_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Select File", "", "KML Files (*.kml)")
        if file_path:
            self.file_input.setText(file_path)
            self.log_message(f"Selected KML file path: {file_path}")

    def generate_kml(self):
        # Get user inputs
        user = self.user_input.text()
        password = self.password_input.text()
        host = self.host_input.text()
        port = self.port_input.text()
        database = self.database_input.text()
        table_name = self.table_input.text()
        kml_path = self.file_input.text()

        if not (user and password and database and table_name and kml_path):
            QMessageBox.warning(self, 'Input Error', 'Please fill in all fields.')
            self.log_message("Error: Please fill in all fields.")
            return

        self.log_message("Starting KML generation...")

        # Create SQLAlchemy engine for PostgreSQL
        try:
            engine = create_engine(f'postgresql://{user}:{password}@{host}:{port}/{database}')
            self.log_message("Connecting to the database...")

            # Query the table and load it into a GeoDataFrame
            sql_query = f'SELECT * FROM {table_name}'
            gdf = gpd.read_postgis(sql_query, engine, geom_col='geometry')  # Assuming geometry column is named 'geometry'
            self.log_message(f"Query executed: {sql_query}")

            # Reproject to geographic coordinates (lat/lon, WGS 84)
            gdf = gdf.to_crs(epsg=4326)
            self.log_message("Reprojected GeoDataFrame to WGS 84 (EPSG: 4326)")

            # Initialize KML object
            kml = Kml()

            # Loop through GeoDataFrame and create KML with extrusion
            for idx, row in gdf.iterrows():
                polygon = row['geometry']
                height = row.get('height', 10)  # Default height to 10 if not present

                if isinstance(polygon, Polygon):  # Check if geometry is a polygon
                    # Get exterior coordinates (lat/lon)
                    exterior_coords = [(coord[0], coord[1], 0) for coord in polygon.exterior.coords]

                    # Create a KML polygon with extrusion
                    pol = kml.newpolygon(name=f'Polygon {idx}',
                                         outerboundaryis=exterior_coords)

                    pol.extrude = 1  # Enable extrusion
                    pol.altitudemode = AltitudeMode.relativetoground  # Altitude relative to ground
                    pol.outerboundaryis = [(coord[0], coord[1], height) for coord in polygon.exterior.coords]  # Add height to each point

                    # Optionally style the polygon
                    pol.style.polystyle.color = '7d0000ff'  # Red color with transparency
                    pol.style.polystyle.fill = 1

            # Save KML file
            kml.save(kml_path)
            QMessageBox.information(self, 'Success', f'KML file saved at {kml_path}')
            self.log_message(f"KML file saved at {kml_path}")

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'An error occurred: {str(e)}')
            self.log_message(f"Error: {str(e)}")

    def log_message(self, message):
        self.console_log.append(message)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = KMLGeneratorApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()