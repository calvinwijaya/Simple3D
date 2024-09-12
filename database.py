import json
import psycopg2
from shapely.geometry import Polygon

def extract_2d_polygon(geometry, vertices):
    """Convert a CityJSON solid geometry into a 2D polygon footprint."""
    footprint_coords = []

    for surface in geometry['boundaries'][0]:
        exterior_ring = surface[0]
        ring_coords = [(vertices[i][0], vertices[i][1]) for i in exterior_ring]
        footprint_coords.append(ring_coords)

    return Polygon(footprint_coords[0])  # Assuming the first ring is the outer boundary

# Load CityJSON file
with open('result/lod1.json') as f:
    cityjson_data = json.load(f)

# Connect to PostgreSQL/PostGIS
conn = psycopg2.connect("dbname=Simple3D user=postgres password=1234 host=localhost port=5432")
cursor = conn.cursor()

# Iterate through CityObjects and insert 2D geometry into PostGIS
for obj_id, cityobject in cityjson_data['CityObjects'].items():
    if 'geometry' in cityobject:
        geom_type = cityobject['geometry'][0]['type']
        
        if geom_type == 'Solid':  # Handle 3D Solids
            geom_2d = extract_2d_polygon(cityobject['geometry'][0], cityjson_data['vertices'])
            wkt_geom = geom_2d.wkt  # Get WKT string representation

            # Insert geometry as WKT string into PostGIS
            cursor.execute("""
                INSERT INTO city_features (geom, name)
                VALUES (ST_GeomFromText(%s, 32749), %s)
            """, (wkt_geom, obj_id))

# Commit and close connection
conn.commit()
cursor.close()
conn.close()
