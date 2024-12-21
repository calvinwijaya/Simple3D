import argparse
import numpy as np #pip install numpy
import laspy #pip install laspy
import CSF #pip install cloth-simulation-filter
from osgeo import gdal, gdalconst, osr, ogr #conda install gdal
import rasterio #pip install rasterio
import geopandas as gpd #pip install geopandas
from rasterstats import zonal_stats #pip install rasterstats
import fiona
import shapely.geometry as sg
import json
import copy
import os
from rasterio.features import geometry_mask
from scipy import ndimage
import sys
gdal.UseExceptions()
gdal.DontUseExceptions()

dir = os.path.dirname(os.path.abspath(__file__))

def read_las(input_file):  
    # Read ground point cloud data from the input file
    lasfile = laspy.read(input_file)

    # Extract x, y, z coordinates and classification
    x = lasfile.x
    y = lasfile.y
    z = lasfile.z
    r = lasfile.red
    g = lasfile.green
    b = lasfile.blue

    # stack data into numpy array
    data = np.column_stack((x, y, z, r, g, b))

    return data

def save_las(result):
    header = laspy.LasHeader(point_format=2, version="1.2")
    las = laspy.LasData(header)
    las.x = result[:, 0]
    las.y = result[:, 1]
    las.z = result[:, 2]
    las.red = result[:, 3]
    las.green = result[:, 4]
    las.blue = result[:, 5]
    las.write(os.path.join(output_folder, "ground.las"))

def csf_filter(input_file, cloth_resolution, slope):
    # read las file
    data = read_las(input_file)
    xyz = data[:, :3]

    csf = CSF.CSF()

    # prameter settings
    csf.params.bSloopSmooth = slope
    csf.params.cloth_resolution = cloth_resolution

    csf.params.time_step = 0.65
    csf.params.class_threshold = 0.5
    csf.params.interations = 500
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
    
    # Filter to store ground only
    result = result[result[:, -1] == 1] # -1 for last column, 1 for ground label

    save_las(result)

def create_dem(input_file, output_file, cell_size, epsg, dem_type):
    # Read point cloud data
    data = read_las(input_file)

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

    # Initialize Z array with NaN values and a count array
    Z = np.full_like(X, fill_value=np.nan, dtype=np.float32)  # Initialize with NaN
    count = np.zeros_like(X, dtype=int)  # Count of points contributing to each cell
    
    for i in range(len(x)):
        # Find the corresponding grid cell
        col = int((x[i] - xmin) / cell_size)
        row = int((y[i] - ymin) / cell_size)
    
        # Ensure that the point is within the valid range of the grid
        if 0 <= row < Z.shape[0] and 0 <= col < Z.shape[1]:
            # Update the Z value and count for each grid cell
            if dem_type == "DTM":
                # Use minimum value for DTM
                if np.isnan(Z[row, col]) or z[i] < Z[row, col]:
                    Z[row, col] = z[i]
            elif dem_type == "DSM":
                # Use maximum value for DSM
                if np.isnan(Z[row, col]) or z[i] > Z[row, col]:
                    Z[row, col] = z[i]
            count[row, col] += 1
    
    # Interpolate NoData values by averaging neighboring cells
    no_data_mask = np.isnan(Z)
    
    # Number of iterations for interpolation
    num_iterations = 15
    
    for iteration in range(num_iterations):
        for row in range(Z.shape[0]):
            for col in range(Z.shape[1]):
                if no_data_mask[row, col]:
                    # Define the neighborhood of the current cell, enlarging at each iteration
                    neighborhood = Z[max(0, row - iteration):min(Z.shape[0], row + iteration + 1),
                                      max(0, col - iteration):min(Z.shape[1], col + iteration + 1)]
    
                    # Exclude NaN values from the neighborhood
                    valid_neighbors = neighborhood[~np.isnan(neighborhood)]
    
                    # Interpolate the NoData value by averaging valid neighbors
                    if len(valid_neighbors) > 0:
                        Z[row, col] = np.mean(valid_neighbors)
    
    # # Apply Gaussian smoothing to the resulting DTM
    # sigma = 15.0  # Adjust the standard deviation based on your requirements
    # Z = ndimage.gaussian_filter(Z, sigma=sigma)

    # Set up the GeoTIFF driver
    driver = gdal.GetDriverByName("GTiff")

    # Create the output GeoTIFF file
    dtm_ds = driver.Create(output_file, len(x_grid), len(y_grid), 1, gdal.GDT_Float32)

    # Define the spatial reference system
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)  # Assuming WGS84

    # Set the geotransform (origin and pixel size)
    dtm_ds.SetGeoTransform((xmin, cell_size, 0, ymin, 0, cell_size))

    # Set the spatial reference
    dtm_ds.SetProjection(srs.ExportToWkt())

    # Write the DTM data to the GeoTIFF
    dtm_ds.GetRasterBand(1).WriteArray(Z)

    # Close the GeoTIFF dataset
    dtm_ds = None

def create_ohm(dsm_path, dtm_path, output_path):
    # Open DSM and DTM raster files
    with rasterio.open(dsm_path) as dsm_src, rasterio.open(dtm_path) as dtm_src:
        # Read raster data as numpy arrays
        dsm = dsm_src.read(1, masked=True)
        dtm = dtm_src.read(1, masked=True)

        # Check dimensions and adjust if necessary
        if dsm.shape != dtm.shape:
            # Calculate new dimensions
            min_height = min(dsm.shape[0], dtm.shape[0])
            min_width = min(dsm.shape[1], dtm.shape[1])
            
            # Crop both arrays to the minimum dimensions
            dsm = dsm[:min_height, :min_width]
            dtm = dtm[:min_height, :min_width]
        
        # Subtract DTM from DSM to create OHM
        ohm = dsm - dtm

        # Update the metadata for the output file
        meta = dsm_src.meta.copy()
        meta.update(dtype=rasterio.float32, count=1)

        # Write the OHM to a new raster file
        with rasterio.open(output_path, 'w', **meta) as dst:
            dst.write(ohm.astype(rasterio.float32), 1)

def zonal_statistics(vector_path, ohm, epsg):
    # Load vector data
    gdf = gpd.read_file(vector_path)

    # Load raster data
    with rasterio.open(ohm) as raster:
    
        # Define function to compute zonal statistics for each feature
        def compute_zonal_statistics(vector_data, raster_data):
            mean_values = []  # List to store mean values
            # Iterate over vector features
            for index, feature in vector_data.iterrows():
                # Extract geometry of the feature
                geometry = feature.geometry

                # Mask raster with feature geometry
                mask = geometry_mask([geometry], raster_data.shape, raster_data.transform, invert=True)

                # Apply mask to raster data
                masked_raster = raster_data.read(1, masked=True)

                # Extract values within the masked area
                values_within_mask = masked_raster[mask]

                # Compute statistics (e.g., mean, median)
                if values_within_mask.size > 0 and not np.all(np.isnan(values_within_mask)):
                    mean_value = np.mean(values_within_mask)
                    # mean_value = np.max(values_within_mask)
                else:
                    mean_value = np.nan  # Set to NaN if no valid values

                # Append mean value to the list
                mean_values.append(mean_value)

            return mean_values

        # Compute zonal statistics
        mean_values = compute_zonal_statistics(gdf, raster)

        # Add the results to the GeoDataFrame
        gdf['height'] = mean_values

        # Set CRS
        gdf.crs = epsg

        # Specify the GeoPackage path
        geopackage_path = os.path.join(output_folder,'zonal stat.gpkg')
        # geojson_path = os.path.join(output_folder,'zonal stat.geojson')

        # Clean up the data by replacing masked values (NaN) with None
        # gdf = gdf.applymap(lambda x: None if isinstance(x, np.ma.core.MaskedConstant) else x)

        # Save the GeoDataFrame to GeoPackage
        gdf.to_file(geopackage_path, layer='buildings', driver='GPKG')

def generate_lod1(output):
    #-- read the input footprints
    c = fiona.open(os.path.join(output_folder,'zonal stat.gpkg'))
    print("Number of buildings: ", len(c))
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
    print("LOD1 City Model Generation Complete!")

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
    # cm['CityObjects'][attributes['id']] = oneb
    city_objects_key = 'id' if 'id' in attributes else 'Id'
    cm['CityObjects'][attributes[city_objects_key]] = oneb

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

def check_args(args):
    # Ensure that either --point_cloud is provided or both --dsm and --dtm
    if args.point_cloud:
        if args.dsm or args.dtm:
            print("Error: If --point_cloud is provided, --dsm and --dtm must not be specified.")
            sys.exit(1)
    elif args.dsm and args.dtm:
        # Both dsm and dtm must be provided together
        pass
    else:
        print("Error: You must provide either --point_cloud or both --dsm and --dtm.")
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate LOD1')
    parser.add_argument('--point_cloud', type=str, help='Directory for point cloud data')
    parser.add_argument('--dsm', type=str, help='File path for DSM (Digital Surface Model)')
    parser.add_argument('--dtm', type=str, help='File path for DTM (Digital Terrain Model)')
    parser.add_argument('--building_outline', type=str, required=True, help='Directory for building vector data')
    parser.add_argument('--cell_size', type=float, default=1.0, help='Cell Size for creating DSM and DTM')
    parser.add_argument('--cloth_resolution', type=float, default=2.0, help='Grid size to cover the terrain')
    parser.add_argument('--slope', type=bool, default=True, help='Option to process steep slopes')
    parser.add_argument('--epsg', type=int, required=True, help='EPSG code for the data reference system')
    parser.add_argument('--output', type=str, required=True, help='Output directory to save results')
    args = parser.parse_args()

    # Validate arguments
    check_args(args)
    
    # Define the output folder path
    output_folder = args.output

    # Create the output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    else:
        pass

    # Output directory
    ground = os.path.join(output_folder, "ground.las")
    dtm = os.path.join(output_folder, "dtm.tif")
    dsm = os.path.join(output_folder, "dsm.tif")
    ohm = os.path.join(output_folder, "ohm.tif")
    lod1 = os.path.join(output_folder, "lod1.json")

    if args.point_cloud:
        print("Filtering Point Cloud")
        csf_filter(args.point_cloud, args.cloth_resolution, args.slope)

        print("Generate DTM")
        create_dem(ground, dtm, args.cell_size, args.epsg, "DTM")

        print("Generate DSM")
        create_dem(args.point_cloud, dsm, args.cell_size, args.epsg, "DSM")
    else:
        print(f"Using provided DSM: {args.dsm} and DTM: {args.dtm}")
        dsm = args.dsm
        dtm = args.dtm
    
    print("OHM Calculation")
    create_ohm(dsm, dtm, ohm)

    print("Calculate Zonal Statistics")
    zonal_statistics(args.building_outline, ohm, args.epsg)
    
    print("Create 3D City LOD1")
    generate_lod1(lod1)