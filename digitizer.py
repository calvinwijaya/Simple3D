from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QFileDialog, QMessageBox, QGraphicsView, QGraphicsScene, QGraphicsLineItem, QGraphicsPolygonItem
)
from PyQt5.QtGui import (
    QPixmap, QPolygonF, QImage, QPen, QColor, QBrush
)
from PyQt5.QtCore import Qt, QPointF, QLineF
from shapely.geometry import Polygon, mapping
import json
import numpy as np
from osgeo import gdal
import sys

class DigitizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Orthophoto Polygon Digitizer")
        self.initUI()
        self.image_loaded = False
        self.digitizing_mode = False  # To track whether we are in digitizing mode
        self.selected_polygon_item = None  # To track the selected polygon for deletion
        self.polygon_id_counter = 1  # Initialize the polygon ID counter
        self.panning = False  # Variable to track panning state
        self.temp_points = []  # Temporary points for the polygon being drawn
        self.temp_item = None  # Temporary QGraphicsPolygonItem for visualization
        self.resize(800, 800)

    def initUI(self):
        # Create menu actions
        open_action = QAction('Open Image', self)
        open_action.triggered.connect(self.open_image)

        save_action = QAction('Save GeoJSON', self)
        save_action.triggered.connect(self.save_geojson)

        start_digitizing_action = QAction('Start Digitizing', self)
        start_digitizing_action.triggered.connect(self.start_digitizing)

        stop_digitizing_action = QAction('Stop Digitizing', self)
        stop_digitizing_action.triggered.connect(self.stop_digitizing)

        delete_polygon_action = QAction('Delete Selected Polygon', self)
        delete_polygon_action.triggered.connect(self.delete_selected_polygon)

        # Add actions to the menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)

        edit_menu = menubar.addMenu('Edit')
        edit_menu.addAction(start_digitizing_action)
        edit_menu.addAction(stop_digitizing_action)
        edit_menu.addAction(delete_polygon_action)

        # Set up the graphics view
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)

        # Store digitized geometries
        self.geometries = []

        # Enable mouse tracking and set mouse events
        self.view.setMouseTracking(True)
        self.view.mousePressEvent = self.mouse_press_event
        self.view.mouseMoveEvent = self.mouse_move_event
        self.view.mouseReleaseEvent = self.mouse_release_event

    def wheelEvent(self, event):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # Check the scroll direction
        if event.angleDelta().y() > 0:
            # Zoom in
            self.view.scale(zoom_in_factor, zoom_in_factor)
        else:
            # Zoom out
            self.view.scale(zoom_out_factor, zoom_out_factor)
    
    def mouse_press_event(self, event):
        if not self.image_loaded:
            return

        if self.digitizing_mode:  # Only allow digitizing when in digitizing mode
            if event.button() == Qt.LeftButton:
                pos = self.view.mapToScene(event.pos())
                x, y = pos.x(), pos.y()

                # Convert screen coordinates to geospatial coordinates
                geo_x, geo_y = self.screen_to_geo(x, y)
                self.temp_points.append((x, y))

                # Update temporary polygon item
                if self.temp_item:
                    self.scene.removeItem(self.temp_item)
                polygon = QPolygonF([QPointF(px, py) for px, py in self.temp_points])
                self.temp_item = QGraphicsPolygonItem(polygon)
                pen = QPen(Qt.red, 2)
                self.temp_item.setPen(pen)
                self.scene.addItem(self.temp_item)

                # Draw temporary lines for visual aid
                if len(self.temp_points) > 1:
                    line = QGraphicsLineItem(QLineF(QPointF(*self.temp_points[-2]), QPointF(*self.temp_points[-1])))
                    self.scene.addItem(line)

            elif event.button() == Qt.RightButton and len(self.temp_points) > 2:
                # Close the polygon by connecting the last point to the first
                self.temp_points.append(self.temp_points[0])

                # Finalize the polygon when right-clicked
                points = [self.screen_to_geo(x, y) for x, y in self.temp_points]
                polygon = Polygon(points)
                # Assign an ID to the polygon and store the geometry with ID
                polygon_item = QGraphicsPolygonItem(QPolygonF([QPointF(x, y) for x, y in self.temp_points]))
                polygon_item.setPen(QPen(Qt.red, 2))
                polygon_item.setBrush(QBrush(QColor(255, 0, 0, 100)))  # Semi-transparent fill
                polygon_item.setData(0, self.polygon_id_counter)  # Store the ID in the polygon item

                self.geometries.append({
                    "id": self.polygon_id_counter,
                    "geometry": polygon,
                    "graphics_item": polygon_item
                })
                self.scene.addItem(polygon_item)

                # Increment the polygon ID counter for the next polygon
                self.polygon_id_counter += 1

                # Clear temporary items
                self.temp_points = []
                if self.temp_item:
                    self.temp_item = None

        else:
            if event.button() == Qt.LeftButton:
                # Deselect any previously selected polygon
                if self.selected_polygon_item:
                    self.selected_polygon_item.setPen(QPen(Qt.red, 2))  # Revert to the original color
                    self.selected_polygon_item = None

                # Detect polygon under mouse for selection
                pos = self.view.mapToScene(event.pos())
                items = self.scene.items(pos)
                for item in items:
                    if isinstance(item, QGraphicsPolygonItem):
                        item.setPen(QPen(Qt.blue, 2))  # Highlight the selected polygon
                        self.selected_polygon_item = item
                        break

            if event.button() == Qt.MiddleButton:  # Start panning when the middle mouse button is pressed
                self.panning = True
                self.pan_start = event.pos()  # Store the starting point for panning

    def mouse_move_event(self, event):
        if self.panning:
            delta = event.pos() - self.pan_start  # Calculate the difference between the current and starting positions
            self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() - delta.x())
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() - delta.y())
            self.pan_start = event.pos()  # Update the starting point for panning

    def mouse_release_event(self, event):
        if event.button() == Qt.MiddleButton:
            self.panning = False  # Stop panning when the middle mouse button is released

    def screen_to_geo(self, x, y):
        # Map screen coordinates to geospatial coordinates
        gt = self.geotransform
        geo_x = gt[0] + x * gt[1] + y * gt[2]
        geo_y = gt[3] + x * gt[4] + y * gt[5]
        return geo_x, geo_y

    def open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Orthophoto", "", "Image Files (*.tif *.tiff)"
        )
        if file_path:
            # Load the image using GDAL
            dataset = gdal.Open(file_path)
            if not dataset:
                QMessageBox.critical(self, "Error", "Failed to load the image.")
                return

            # Get geotransform and projection
            self.geotransform = dataset.GetGeoTransform()
            self.projection = dataset.GetProjection()

            # Read the RGB bands
            r_band = dataset.GetRasterBand(1).ReadAsArray()
            g_band = dataset.GetRasterBand(2).ReadAsArray()
            b_band = dataset.GetRasterBand(3).ReadAsArray()

            # Combine into an RGB array
            rgb_array = np.dstack((r_band, g_band, b_band))

            # Convert the RGB array into QImage
            height, width, _ = rgb_array.shape
            bytes_per_line = 3 * width
            image = QImage(rgb_array.data, width, height, bytes_per_line, QImage.Format_RGB888)

            # Convert QImage to QPixmap
            pixmap = QPixmap.fromImage(image)

            # Display the image in the scene
            self.scene.clear()
            self.scene.addPixmap(pixmap)  # Use the pixmap here
            self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            self.image_loaded = True

    def start_digitizing(self):
        self.digitizing_mode = True
        QMessageBox.information(self, "Digitizing Mode", "Digitizing mode activated. Click to start drawing polygons.")

    def stop_digitizing(self):
        self.digitizing_mode = False
        QMessageBox.information(self, "Digitizing Mode", "Digitizing mode deactivated.")
    
    def delete_selected_polygon(self):
        if self.selected_polygon_item:
            # Find the corresponding geometry in the geometries list
            polygon_id = self.selected_polygon_item.data(0)
            self.geometries = [geom for geom in self.geometries if geom["id"] != polygon_id]
            self.scene.removeItem(self.selected_polygon_item)  # Remove the selected polygon from the scene
            self.selected_polygon_item = None  # Clear the selected polygon
            QMessageBox.information(self, "Polygon Deleted", "The selected polygon has been deleted.")
        else:
            QMessageBox.warning(self, "No Selection", "No polygon selected. Please select a polygon to delete.")

    def save_geojson(self):
        if not self.geometries:
            QMessageBox.information(self, "No Data", "No geometries to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save GeoJSON", "", "GeoJSON Files (*.geojson)"
        )
        if file_path:
            features = []
            for geom_data in self.geometries:
                geom = geom_data["geometry"]
                features.append({
                    "type": "Feature",
                    "properties": {
                        "id": geom_data["id"]  # Include the ID in properties
                    },
                    "geometry": mapping(geom)  # Convert to GeoJSON format using mapping
                })
            geojson_data = {
                "type": "FeatureCollection",
                "features": features
            }
            with open(file_path, 'w') as f:
                json.dump(geojson_data, f)
            QMessageBox.information(self, "Success", "GeoJSON file saved successfully.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DigitizerApp()
    window.show()
    sys.exit(app.exec_())
