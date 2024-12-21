from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QFileDialog, QMessageBox, QHBoxLayout, QTextEdit
)
from PyQt5.QtGui import QIcon, QPixmap
from sqlalchemy import create_engine
import geopandas as gpd
import sys

class database_gui(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Set up main layout
        layout = QVBoxLayout()

        # GeoPackage Path Input with "Browse" button
        geopackage_layout = QHBoxLayout()
        self.geopackage_label = QLabel("Data Path:")
        self.geopackage_input = QLineEdit(self)
        self.geopackage_input.setReadOnly(True)
        self.geopackage_browse_button = QPushButton('...', self)
        self.geopackage_browse_button.clicked.connect(self.browse_geopackage)

        geopackage_layout.addWidget(self.geopackage_input)
        geopackage_layout.addWidget(self.geopackage_browse_button)

        # Add GeoPackage widgets to layout
        layout.addWidget(self.geopackage_label)
        layout.addLayout(geopackage_layout)

        # PostgreSQL Connection Details
        self.user_label = QLabel("Username:")
        self.user_input = QLineEdit()

        self.password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        self.host_label = QLabel("Host:")
        self.host_input = QLineEdit("localhost")

        self.port_label = QLabel("Port:")
        self.port_input = QLineEdit("5432")

        self.database_name_label = QLabel("Database:")
        self.database_name_input = QLineEdit()

        # Submit Button
        self.submit_button = QPushButton("Import Data")
        self.submit_button.clicked.connect(self.import_data)

        # Log Console
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setPlaceholderText("Console log...")

        # Add widgets to layout
        layout.addWidget(self.user_label)
        layout.addWidget(self.user_input)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.host_label)
        layout.addWidget(self.host_input)
        layout.addWidget(self.port_label)
        layout.addWidget(self.port_input)
        layout.addWidget(self.database_name_label)
        layout.addWidget(self.database_name_input)
        layout.addWidget(self.submit_button)
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

        # Set the layout
        self.setLayout(layout)
        self.setWindowTitle("PostgreSQL Importer")
        self.setGeometry(100, 100, 800, 600)

    def browse_geopackage(self):
        # Browse for GeoPackage file
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select GeoPackage File", "", "GeoPackage Files (*.gpkg);;All Files (*)", options=options)
        if file_path:
            self.geopackage_input.setText(file_path)

    def import_data(self):
        try:
            # Get user inputs
            geopackage_path = self.geopackage_input.text()
            layer_name = "buildings"
            user = self.user_input.text()
            password = self.password_input.text()
            host = self.host_input.text()
            port = self.port_input.text()
            database_name = self.database_name_input.text()

            # Check if all inputs are provided
            if not geopackage_path or not layer_name or not user or not password or not database_name:
                self.log_console.append("Input Error: Please fill in all required fields.")
                QMessageBox.warning(self, "Input Error", "Please fill in all required fields.")
                return

            # Read GeoPackage file as GeoDataFrame
            self.log_console.append(f"Reading GeoPackage file from: {geopackage_path}")
            gdf = gpd.read_file(geopackage_path, layer=layer_name)
            self.log_console.append("GeoPackage file successfully read.")

            # Create an SQLAlchemy engine
            connection_string = f'postgresql://{user}:{password}@{host}:{port}/{database_name}'
            self.log_console.append(f"Connecting to PostgreSQL database at {host}:{port}")
            engine = create_engine(connection_string)

            # Write GeoDataFrame to PostGIS table
            self.log_console.append("Writing GeoDataFrame to PostGIS...")
            gdf.to_postgis(name='building', con=engine, if_exists='replace', index=False)
            self.log_console.append("Data successfully imported to the database!")

            # Show success message
            QMessageBox.information(self, "Success", "Data successfully imported to the database!")

        except Exception as e:
            # Log and show error message if something goes wrong
            error_message = f"An error occurred: {str(e)}"
            self.log_console.append(error_message)
            QMessageBox.critical(self, "Error", error_message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = database_gui()
    window.show()
    sys.exit(app.exec_())