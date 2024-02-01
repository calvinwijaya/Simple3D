import argparse
import numpy as np
import laspy
import CSF
from osgeo import gdal, gdalconst, osr
import rasterio
import geopandas as gpd
from rasterstats import zonal_stats
import fiona
import shapely.geometry as sg
import json
import copy
gdal.UseExceptions()
gdal.DontUseExceptions()

def csf_filter(input_file):
    inFile = laspy.read(input_file) # read a las file
    x = inFile.x
    y = inFile.y
    z = inFile.z
    r = inFile.red
    g = inFile.green
    b = inFile.blue
    data = np.column_stack((x, y, z, r, g, b))

    points = inFile.points
    xyz = np.vstack((inFile.x, inFile.y, inFile.z)).transpose() # extract x, y, z and put into a list

    csf = CSF.CSF()

    # prameter settings
    csf.params.bSloopSmooth = True
    csf.params.cloth_resolution = 0.5
    # more details about parameter: http://ramm.bnu.edu.cn/projects/CSF/download/

    csf.setPointCloud(xyz)
    ground = CSF.VecInt()  # a list to indicate the index of ground points after calculation
    non_ground = CSF.VecInt() # a list to indicate the index of non-ground points after calculation
    csf.do_filtering(ground, non_ground) # do actual filtering.

    # Convert filtering result to array
    ground_arr = np.array(ground)
    non_ground_arr = np.array(non_ground)

    # Create an array for classification with zeros for non-ground points and ones for ground points
    classification_ground = np.ones_like(ground_arr)
    classification_non_ground = np.zeros_like(non_ground_arr)

    # Combine the ground and non-ground classification arrays
    classification = np.concatenate((classification_non_ground, classification_ground), axis=0)

    # Combine the X, Y, Z, R, G, B, and classification arrays for ground and non-ground
    ground_data = np.column_stack((ground_arr, classification_ground))
    non_ground_data = np.column_stack((non_ground_arr, classification_non_ground))

    # Combine the ground and non-ground data arrays
    result = np.concatenate((ground_data, non_ground_data), axis=0)

    # Sort the result array based on the original point IDs
    result = result[result[:, 0].argsort()]

    # Extract the second column (classification) from the result array
    classification_column = result[:, 1]

    # Add the classification column to the original data array
    result = np.column_stack((data, classification_column))

    header = laspy.LasHeader(point_format=2, version="1.2")
    las = laspy.LasData(header)
    las.x = result[:, 0]
    las.y = result[:, 1]
    las.z = result[:, 2]
    las.red = result[:, 3]
    las.green = result[:, 4]
    las.blue = result[:, 5]
    las.classification = result[:, 6]
    las.write("data/data.las")


def read_las(input_file):  
    # Read ground point cloud data from the input file
    lasfile = laspy.read(input_file)

    # Extract x, y, z coordinates and classification
    x = lasfile.x
    y = lasfile.y
    z = lasfile.z
    C = lasfile.classification

    # stack data into numpy array
    data = np.column_stack((x, y, z, C))

    return data

def filter_ground(data):
    # Replace column names
    column_names = ['X', 'Y', 'Z', 'C']
    
    # Find the index of the 'Classification' column
    c_column_index = column_names.index('C')
    
    # Filter rows where the 'Classification' column is equal to 1 (Ground)
    data = data[data[:, c_column_index] == 1]

    return data

def create_dem(input_file, output_file, cell_size, type='dtm'):
    # Read point cloud data
    data = read_las(input_file)

    # Filter ground point cloud data
    if type == 'dtm':
        data = filter_ground(data)
    else:
        pass

    # Extract x, y, and z coordinates
    x = data[:, 0]
    y = data[:, 1]
    z = data[:, 2]
    
    # Define the extent of the DTM
    xmin, xmax, ymin, ymax = min(x), max(x), min(y), max(y)

    # Create a grid based on the specified cell size
    x_grid = np.arange(xmin, xmax, cell_size)
    y_grid = np.arange(ymin, ymax, cell_size)

    # Create a meshgrid
    X, Y = np.meshgrid(x_grid, y_grid)

    # Binning Minimum Value method
    Z = np.full_like(X, fill_value=np.nan)  # Initialize with NaN
    count = np.zeros_like(X, dtype=int)  # Count of points contributing to each cell
    
    for i in range(len(x)):
        # Find the corresponding grid cell
        col = int((x[i] - xmin) / cell_size)
        row = int((y[i] - ymin) / cell_size)
    
        # Ensure that the point is within the valid range of the grid
        if 0 <= row < Z.shape[0] and 0 <= col < Z.shape[1]:
            # Update the Z value and count for each grid cell
            if np.isnan(Z[row, col]) or z[i] < Z[row, col]:
                Z[row, col] = z[i]
            count[row, col] += 1
    
    # Interpolate NoData values by averaging neighboring cells with multiple iterations
    no_data_mask = np.isnan(Z)
    
    # Number of iterations
    num_iterations = 15
    
    for iteration in range(num_iterations):
        for row in range(Z.shape[0]):
            for col in range(Z.shape[1]):
                if no_data_mask[row, col]:
                    # Define the neighborhood of the current cell, enlarging at each iteration
                    neighborhood = Z[max(0, row - iteration):min(Z.shape[0], row + iteration + 1),
                                      max(0, col - iteration):min(Z.shape[1], col + iteration + 1)]
    
                    # Exclude NaN and NoData values from the neighborhood
                    valid_neighbors = neighborhood[~np.isnan(neighborhood) & ~no_data_mask[max(0, row - iteration):min(Z.shape[0], row + iteration + 1),
                                                                                           max(0, col - iteration):min(Z.shape[1], col + iteration + 1)]]
    
                    # Interpolate the NoData value by averaging valid neighbors
                    if len(valid_neighbors) > 0:
                        Z[row, col] = np.mean(valid_neighbors)
    
    # Optionally, apply minimum value for each grid cell again
    min_elevation = np.nanmin(Z)
    Z[np.isnan(Z)] = min_elevation

    # Apply Gaussian smoothing to the resulting DTM
    # sigma = 15.0  # Adjust the standard deviation based on your requirements
    # Z = scipy.ndimage.gaussian_filter(Z, sigma=sigma)

    # Set up the GeoTIFF driver
    driver = gdal.GetDriverByName("GTiff")

    # Create the output GeoTIFF file
    dtm_ds = driver.Create(output_file, len(x_grid), len(y_grid), 1, gdalconst.GDT_Float32)

    # Define the spatial reference system
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32748)  # Assuming WGS84

    # Set the geotransform (origin and pixel size)
    dtm_ds.SetGeoTransform((xmin, cell_size, 0, ymax, 0, -cell_size))

    # Set the spatial reference
    dtm_ds.SetProjection(srs.ExportToWkt())

    # Write the DTM data to the GeoTIFF
    dtm_ds.GetRasterBand(1).WriteArray(Z)

    # Close the GeoTIFF dataset
    dtm_ds = None

def create_normalized_dsm(dsm_path, dtm_path, output_path):
    # Open DSM and DTM raster files
    with rasterio.open(dsm_path) as dsm_src, rasterio.open(dtm_path) as dtm_src:
        # Read raster data as numpy arrays
        dsm = dsm_src.read(1, masked=True)
        dtm = dtm_src.read(1, masked=True)

        # Subtract DTM from DSM to create nDSM
        ndsm = dsm - dtm

        # Update the metadata for the output file
        meta = dsm_src.meta.copy()
        meta.update(dtype=rasterio.float32, count=1)

        # Write the nDSM to a new raster file
        with rasterio.open(output_path, 'w', **meta) as dst:
            dst.write(ndsm.astype(rasterio.float32), 1)

def zonal_statistics(vector_path, ndsm):
    gdf = gpd.read_file(vector_path)

    # Load raster data
    ndsm = 'data/ndsm.tif'

    # Perform the zonal statistics
    result = zonal_stats(gdf, ndsm, stats=['mean'])

    # Add the results to the GeoDataFrame
    gdf['height'] = [feature['mean'] for feature in result]

    # Specify the GeoPackage path
    geopackage_path = 'data/buildings.gpkg'

    # Save the GeoDataFrame to GeoPackage
    gdf.to_file(geopackage_path, layer='buildings', driver='GPKG')

def generate_lod1(output):
    #-- read the input footprints
    c = fiona.open('data/buildings.gpkg')
    print("Jumlah bangunan: ", len(c))
    lsgeom = [] #-- list of the geometries
    lsattributes = [] #-- list of the attributes
    for each in c:
        lsgeom.append(sg.shape(each['geometry'])) #-- geom are casted to Fiona's 
        lsattributes.append(each['properties'])
    #-- extrude to CityJSON
    cm = output_citysjon(lsgeom, lsattributes)
    #-- save the file to disk 'mycitymodel.json'
    json_str = json.dumps(cm, indent=2)
    fout = open(output, "w")
    fout.write(json_str)
    print("Pembuatan Bangunan LOD1 Selesai")

def output_citysjon(lsgeom, lsattributes):
    #-- create the JSON data structure for the City Model
    cm = {}
    cm["type"] = "CityJSON"
    cm["version"] = "0.9"
    cm["CityObjects"] = {}
    cm["vertices"] = []

    for (i, geom) in enumerate(lsgeom):
        if isinstance(geom, sg.MultiPolygon):
            # If the geometry is a MultiPolygon, iterate over its constituent polygons
            for polygon in geom.geoms:
                process_building_polygon(polygon.exterior, polygon.interiors, lsattributes[i], cm)
        else:
            # If it's a regular Polygon, process it directly
            process_building_polygon(geom.exterior, geom.interiors, lsattributes[i], cm)

    return cm

def process_building_polygon(footprint_exterior, footprint_interiors, attributes, cm):
    # Process the building polygon and add to the CityJSON structure
    oneb = {}
    oneb['type'] = 'Building'
    oneb['attributes'] = {}

    # insert attributes if any
    # oneb['attributes']['local-id'] = attributes['lokaalid']
    # oneb['attributes']['bgt_status'] = attributes['bgt_status']
    
    oneb['geometry'] = []  # a cityobject can have >1
    # the geometry
    g = {}
    g['type'] = 'Solid'
    g['lod'] = 1
    allsurfaces = []  # list of surfaces forming the oshell of the solid
    # exterior ring of each footprint
    oring = list(footprint_exterior.coords)
    oring.pop()  # remove last point since first==last
    if footprint_exterior.is_ccw == False:
        # to get proper orientation of the normals
        oring.reverse()
    extrude_walls(oring, attributes['height'], allsurfaces, cm)
    # interior rings of each footprint
    irings = []
    for interior in footprint_interiors:
        iring = list(interior.coords)
        iring.pop()  # remove last point since first==last
        if interior.is_ccw == True:
            # to get proper orientation of the normals
            iring.reverse()
        irings.append(iring)
        extrude_walls(iring, attributes['height'], allsurfaces, cm)
    # top-bottom surfaces
    extrude_roof_ground(oring, irings, attributes['height'], False, allsurfaces, cm)
    extrude_roof_ground(oring, irings, 0, True, allsurfaces, cm)
    # add the extruded geometry to the geometry
    g['boundaries'] = []
    g['boundaries'].append(allsurfaces)
    # add the geom to the building
    oneb['geometry'].append(g)
    
    # insert the building as one new city object
    # this will work as unique id or identifier
    # cm['CityObjects'][attributes['gml_id']] = oneb
    cm['CityObjects'][attributes['Id']] = oneb

def extrude_roof_ground(orng, irngs, height, reverse, allsurfaces, cm):
    oring = copy.deepcopy(orng)
    irings = copy.deepcopy(irngs)
    if reverse == True:
        oring.reverse()
        for each in irings:
            each.reverse()
    for (i, pt) in enumerate(oring):
        cm['vertices'].append([pt[0], pt[1], height])
        oring[i] = (len(cm['vertices']) - 1)
    for (i, iring) in enumerate(irings):
        for (j, pt) in enumerate(iring):
            cm['vertices'].append([pt[0], pt[1], height])
            irings[i][j] = (len(cm['vertices']) - 1)
    # print(oring)
    output = []
    output.append(oring)
    for each in irings:
        output.append(each)
    allsurfaces.append(output)

def extrude_walls(ring, height, allsurfaces, cm):
    #-- each edge become a wall, ie a rectangle
    for (j, v) in enumerate(ring[:-1]):
        l = []
        cm['vertices'].append([ring[j][0],   ring[j][1],   0])
        cm['vertices'].append([ring[j+1][0], ring[j+1][1], 0])
        cm['vertices'].append([ring[j+1][0], ring[j+1][1], height])
        cm['vertices'].append([ring[j][0],   ring[j][1],   height])
        t = len(cm['vertices'])
        allsurfaces.append([[t-4, t-3, t-2, t-1]])    
    #-- last-first edge
    l = []
    cm['vertices'].append([ring[-1][0], ring[-1][1], 0])
    cm['vertices'].append([ring[0][0],  ring[0][1],  0])
    cm['vertices'].append([ring[0][0],  ring[0][1],  height])
    cm['vertices'].append([ring[-1][0], ring[-1][1], height])
    t = len(cm['vertices'])
    allsurfaces.append([[t-4, t-3, t-2, t-1]])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate LOD1')
    parser.add_argument('--data_las', type=str, default='', help='Directory for point cloud data')
    parser.add_argument('--data_building', type=str, default='', help='Directory for building vector data')
    parser.add_argument('--output', type=str, default="data/model_lod1.json", help='Directory for save LOD1')
    parser.add_argument('--cell_size', type=int, default=1, help='Cell Size for creating DSM and DTM')
    args = parser.parse_args()

    # Output directory
    data = "data/data.las"
    dtm = "data/dtm.tif"
    dsm = "data/dsm.tif"
    ndsm = 'data/ndsm.tif'

    print("Filtering Point Cloud")
    csf_filter(args.data_las)

    print("Pembuatan DTM")
    create_dem(data, dtm, args.cell_size, type='dtm')
    print("Hasil DTM disimpan di", dtm)

    print("Pembuatan DSM")
    create_dem(args.data_las, dsm, args.cell_size, type='dsm')
    print("Hasil DSM disimpan di", dsm)

    print("Perhitungan nDSM. nDSM = DTM - DSM")
    create_normalized_dsm(dsm, dtm, ndsm)
    zonal_statistics(args.data_building, ndsm)
    generate_lod1(args.output)