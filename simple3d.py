import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout
from PyQt5.QtGui import QIcon
from lod1 import CityModelGUI
from digitizer import DigitizerApp
from database import database_gui
from kml import KMLGeneratorApp

class IntegratedApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple3D")
        self.setGeometry(100, 100, 1000, 800)
        
        # Create a tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Create the first tab for the City Model GUI
        self.city_model_tab = QWidget()
        self.city_model_layout = QVBoxLayout()
        self.city_model_widget = CityModelGUI()
        self.city_model_layout.addWidget(self.city_model_widget)
        self.city_model_tab.setLayout(self.city_model_layout)
        self.tabs.addTab(self.city_model_tab, "City Model Generator")
        
        # Create the second tab for the Digitizer GUI
        self.digitizer_tab = QWidget()
        self.digitizer_layout = QVBoxLayout()
        self.digitizer_widget = DigitizerApp()
        self.digitizer_layout.addWidget(self.digitizer_widget)
        self.digitizer_tab.setLayout(self.digitizer_layout)
        self.tabs.addTab(self.digitizer_tab, "Orthophoto Digitizer")

        # Create the third tab for connect the database
        self.database_tab = QWidget()
        self.database_layout = QVBoxLayout()
        self.database_widget = database_gui()
        self.database_layout.addWidget(self.database_widget)
        self.database_tab.setLayout(self.database_layout)
        self.tabs.addTab(self.database_tab, "Connect Database")

        # Create the fourth tab for export as KML
        self.kmlgen_tab = QWidget()
        self.kmlgen_layout = QVBoxLayout()
        self.kmlgen_widget = KMLGeneratorApp()
        self.kmlgen_layout.addWidget(self.kmlgen_widget)
        self.kmlgen_tab.setLayout(self.kmlgen_layout)
        self.tabs.addTab(self.kmlgen_tab, "Export 3D KML")
        
        # Set the window icon
        self.setWindowIcon(QIcon("ui/logo.png"))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = IntegratedApp()
    main_window.show()
    sys.exit(app.exec_())
