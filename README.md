![header-01](https://github.com/user-attachments/assets/4090c708-e86a-4535-93a0-e0edbddace97)

# Simple3D
**Simple3D** is simple implementation on how to extrude building outline into LOD1 model. Simple3D is vastly inspired by [GeoCARTA](https://geocarta.id/) (Geospatial-Cadastre with Artificial Intelligence for Generating LOD 3D City Model). While GeoCARTA use automatic and AI processing, Simple3D is a simplification of it by use manual and simple processing. Simple3D aims to create a simple yet effective way to create 3D City in LOD1. Simple3D is in process to publish in national journal. The process or workflow of Simple3D:

![image](https://github.com/user-attachments/assets/5ef6a81f-a59f-45d9-b668-4d646cf128af)

The process is quite simple and straightforward:
1. Input data is building outline and point cloud
2. Filter the point cloud data into ground and off-ground
3. Ground point cloud then used to generate Digital Terrain Model (DTM), while off-ground for Digital Surface Model (DSM)
4. Calculate Object Height Model (OHM) by using formula `OHM = DSM - DTM`
5. Calculate Zonal Statistic from OHM for each building outline
6. Extrude building outline based on OHM as elevation

# How to Use
## Data
The main data only consist of 2 data, building outline and point cloud data!

<img src=https://github.com/user-attachments/assets/ff410f04-8dd8-4c33-a735-146448ef4422 alt="drawing" width="500"/>

Data input used for Simple 3D:
1. Building outline, either can be get from manual digitizing from Orthophoto or automatic way using AI (SAM, etc.), you can use *.GeoJSON or *.shp format.
2. Point Cloud Data, either can be get from Photogrammetry process or UAV LiDAR, you can use *.las format
3. (Optional) DSM and DTM can become an input if user already have the data or the point cloud is already processed. The DSM and DTM are in *.tif or *.tiff format.
Thus, from only at least combination of 2 data (BO + Point Cloud or BO + DSM DTM, you choose!), to create 3D City Model by extrud the BO with elevation from OHM (DSM - DTM).

## Code-Based

```
python main.py --building_outline /directory/to/building_outline.shp --point_cloud /directory/to/point_cloud.las --epsg 4326 --output /directoryforoutput
```

or 

```
python main.py --building_outline /directory/to/building_outline.shp --dsm /directory/to/dsm.tif --dsm /directory/to/dtm.tif --epsg 4326 --output /directoryforoutput
```

## GUI
A
Tab 1:
Tab 2:

<img src=https://github.com/user-attachments/assets/49bb6b91-b1b3-4b96-a3a5-55337105cbb4 alt="drawing" width="1000"/>

# QGIS Plugin
You can also 

<img src=https://github.com/user-attachments/assets/6da764e4-0101-438b-9444-e07f8c054a0d alt="drawing" width="500"/>

# Using This Code?
This repository is free to use for educational and academic purposes. It created as project in Digital Photogrammetry course in Department of Geodetic Engineering, Faculty of Engineering, Universitas Gadjah Mada. You can cite my paper in:
```
@article{,
  title={},
  author={},
  journal={},
  year={2024}
}
