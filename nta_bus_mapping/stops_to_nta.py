"""
Spatial join: assign each MTA bus stop to an NYC Neighborhood Tabulation Area (NTA).
Parses shapefiles and GTFS stops.txt without geopandas/shapely.
"""
import struct
import csv
import json
import sys
import os

# ── Shapefile parser ──

def read_dbf(path):
    """Parse a .dbf file and return list of dicts."""
    with open(path, 'rb') as f:
        header = f.read(32)
        num_records = struct.unpack('<I', header[4:8])[0]
        header_size = struct.unpack('<H', header[8:10])[0]
        record_size = struct.unpack('<H', header[10:12])[0]

        # Read field descriptors
        fields = []
        f.seek(32)
        while True:
            field_header = f.read(32)
            if field_header[0:1] == b'\r':
                break
            name = field_header[:11].split(b'\x00')[0].decode('ascii')
            ftype = chr(field_header[11])
            flen = field_header[16]
            fields.append((name, ftype, flen))

        # Read records
        f.seek(header_size)
        records = []
        for _ in range(num_records):
            rec_data = f.read(record_size)
            if rec_data[0:1] == b'*':  # deleted record
                continue
            offset = 1
            rec = {}
            for name, ftype, flen in fields:
                raw = rec_data[offset:offset+flen]
                val = raw.decode('latin-1').strip()
                rec[name] = val
                offset += flen
            records.append(rec)
    return records, [f[0] for f in fields]


def read_shp_polygons(path):
    """Parse a .shp file and return list of polygon geometries.
    Each geometry is a list of rings (parts). Each ring is list of (x, y)."""
    with open(path, 'rb') as f:
        # File header: 100 bytes
        file_code = struct.unpack('>I', f.read(4))[0]
        assert file_code == 9994, f"Not a shapefile: {file_code}"
        f.seek(24)
        file_length = struct.unpack('>I', f.read(4))[0] * 2  # in bytes
        version = struct.unpack('<I', f.read(4))[0]
        shape_type = struct.unpack('<I', f.read(4))[0]
        f.seek(100)

        geometries = []
        while f.tell() < file_length:
            try:
                rec_num = struct.unpack('>I', f.read(4))[0]
                content_len = struct.unpack('>I', f.read(4))[0] * 2
            except struct.error:
                break

            start = f.tell()
            st = struct.unpack('<I', f.read(4))[0]

            if st == 0:  # Null shape
                geometries.append([])
                f.seek(start + content_len)
                continue

            if st not in (5, 15):  # Polygon or PolygonZ
                f.seek(start + content_len)
                geometries.append([])
                continue

            # Bounding box
            bbox = struct.unpack('<4d', f.read(32))
            num_parts = struct.unpack('<I', f.read(4))[0]
            num_points = struct.unpack('<I', f.read(4))[0]

            parts = [struct.unpack('<I', f.read(4))[0] for _ in range(num_parts)]

            points = []
            for _ in range(num_points):
                x, y = struct.unpack('<2d', f.read(16))
                points.append((x, y))

            # Split into rings by part indices
            rings = []
            for i, start_idx in enumerate(parts):
                end_idx = parts[i+1] if i+1 < len(parts) else num_points
                rings.append(points[start_idx:end_idx])

            geometries.append(rings)

            # Skip any remaining bytes (Z values etc for PolygonZ)
            f.seek(start + content_len)

    return geometries


def point_in_ring(x, y, ring):
    """Ray casting algorithm for point-in-polygon."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_polygon(x, y, rings):
    """Check if point is in polygon (first ring is exterior, rest are holes)."""
    if not rings:
        return False
    if not point_in_ring(x, y, rings[0]):
        return False
    # Check holes
    for ring in rings[1:]:
        if point_in_ring(x, y, ring):
            return False
    return True


def bbox_of_ring(ring):
    """Get bounding box of a ring for quick rejection."""
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def read_stops(path):
    """Read GTFS stops.txt."""
    stops = []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stops.append({
                'stop_id': row['stop_id'],
                'stop_name': row.get('stop_name', ''),
                'stop_lat': float(row['stop_lat']),
                'stop_lon': float(row['stop_lon']),
            })
    return stops


def main():
    # Paths relative to project root (nta_bus/)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    nta_dir = os.path.join(base_dir, 'data', 'nynta2020_26a', 'nynta2020_26a')

    shp_path = os.path.join(nta_dir, 'nynta2020.shp')
    dbf_path = os.path.join(nta_dir, 'nynta2020.dbf')

    # All 5 borough GTFS folders
    borough_folders = {
        'gtfs_bx': 'Bronx',
        'gtfs_b':  'Brooklyn',
        'gtfs_m':  'Manhattan',
        'gtfs_q':  'Queens',
        'gtfs_si': 'Staten Island',
    }

    print("Reading NTA shapefile...")
    records, fields = read_dbf(dbf_path)
    geometries = read_shp_polygons(shp_path)
    print(f"  Found {len(records)} NTA polygons")
    print(f"  DBF fields: {fields}")

    if records:
        print(f"  Sample record: {records[0]}")

    prj_path = os.path.join(nta_dir, 'nynta2020.prj')
    need_transform = False
    if os.path.exists(prj_path):
        with open(prj_path, 'r') as f:
            prj = f.read()
        print(f"\n  Projection: {prj[:120]}...")
        if 'NAD83' in prj or 'State' in prj or 'Plane' in prj or 'feet' in prj.lower() or '2263' in prj:
            need_transform = True
            print("  -> Shapefile is in State Plane (feet). Will convert stops to State Plane.")
        elif 'GCS_WGS_1984' in prj or '4326' in prj:
            print("  -> Shapefile is in WGS84 (lon/lat). No transform needed.")
    else:
        print("  No .prj file found — assuming State Plane EPSG:2263")
        need_transform = True

    # Read stops from all borough GTFS folders
    stops = []
    for folder, boro_label in borough_folders.items():
        stops_path = os.path.join(base_dir, 'data', folder, 'stops.txt')
        if not os.path.exists(stops_path):
            print(f"\n  WARNING: {stops_path} not found, skipping {boro_label}")
            continue
        boro_stops = read_stops(stops_path)
        for s in boro_stops:
            s['gtfs_borough'] = boro_label
        stops.extend(boro_stops)
        print(f"  {boro_label}: {len(boro_stops)} stops from {folder}/")

    # Deduplicate stops that may appear in multiple borough files
    seen = set()
    unique_stops = []
    for s in stops:
        if s['stop_id'] not in seen:
            seen.add(s['stop_id'])
            unique_stops.append(s)
    if len(stops) != len(unique_stops):
        print(f"\n  Deduplicated: {len(stops)} -> {len(unique_stops)} unique stops")
    stops = unique_stops
    print(f"\n  Total stops across all boroughs: {len(stops)}")

    # ── Coordinate transform: WGS84 -> NAD83 State Plane NY Long Island (EPSG:2263) ──
    # Approximate transform using a local Transverse Mercator projection
    # EPSG:2263 params: NAD83, Lambert Conformal Conic
    # Central meridian: -74.0, Lat of origin: 40.166667
    # Standard parallels: 40.666667, 41.033333
    # False easting: 300000 m (984250.0 ft), False northing: 0
    import math

    def wgs84_to_stateplane_2263(lon, lat):
        """Approximate WGS84 to NY State Plane Long Island (EPSG:2263) in US feet.
        Uses Lambert Conformal Conic projection."""
        # Constants for NAD83 / NY Long Island
        a = 6378137.0  # semi-major axis GRS80
        f = 1/298.257222101
        e = math.sqrt(2*f - f*f)

        phi1 = math.radians(40.666667)  # standard parallel 1
        phi2 = math.radians(41.033333)  # standard parallel 2
        phi0 = math.radians(40.166667)  # latitude of origin
        lam0 = math.radians(-74.0)      # central meridian
        FE = 300000.0  # false easting in meters
        FN = 0.0       # false northing in meters

        phi = math.radians(lat)
        lam = math.radians(lon)

        def m_func(phi_):
            return math.cos(phi_) / math.sqrt(1 - e**2 * math.sin(phi_)**2)

        def t_func(phi_):
            es = e * math.sin(phi_)
            return math.tan(math.pi/4 - phi_/2) / ((1-es)/(1+es))**(e/2)

        m1 = m_func(phi1)
        m2 = m_func(phi2)
        t0 = t_func(phi0)
        t1 = t_func(phi1)
        t2 = t_func(phi2)
        t = t_func(phi)

        n = (math.log(m1) - math.log(m2)) / (math.log(t1) - math.log(t2))
        F = m1 / (n * t1**n)
        rho0 = a * F * t0**n
        rho = a * F * t**n
        theta = n * (lam - lam0)

        E = FE + rho * math.sin(theta)
        N = FN + rho0 - rho * math.cos(theta)

        # Convert meters to US survey feet
        us_ft = 0.3048006096012192
        return E / us_ft, N / us_ft

    # Precompute bounding boxes for each NTA polygon
    print("\nBuilding spatial index (bounding boxes)...")
    bboxes = []
    for geom in geometries:
        if geom:
            all_pts = [p for ring in geom for p in ring]
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            bboxes.append((min(xs), min(ys), max(xs), max(ys)))
        else:
            bboxes.append(None)

    # Perform spatial join
    print("Performing spatial join...")
    results = []
    unmatched = 0
    for i, stop in enumerate(stops):
        if (i+1) % 500 == 0:
            print(f"  Processed {i+1}/{len(stops)} stops...")

        if need_transform:
            x, y = wgs84_to_stateplane_2263(stop['stop_lon'], stop['stop_lat'])
        else:
            x, y = stop['stop_lon'], stop['stop_lat']

        matched_nta = None
        for j, (geom, rec) in enumerate(zip(geometries, records)):
            if bboxes[j] is None:
                continue
            bx0, by0, bx1, by1 = bboxes[j]
            if x < bx0 or x > bx1 or y < by0 or y > by1:
                continue
            if point_in_polygon(x, y, geom):
                matched_nta = rec
                break

        if matched_nta:
            results.append({
                'stop_id': stop['stop_id'],
                'stop_name': stop['stop_name'],
                'stop_lat': stop['stop_lat'],
                'stop_lon': stop['stop_lon'],
                'gtfs_borough': stop['gtfs_borough'],
                'NTACode': matched_nta.get('NTA2020', matched_nta.get('NTACode', '')),
                'NTAName': matched_nta.get('NTAName', ''),
                'BoroName': matched_nta.get('BoroName', matched_nta.get('Borough', '')),
                'CountyFIPS': matched_nta.get('CountyFIPS', ''),
            })
        else:
            results.append({
                'stop_id': stop['stop_id'],
                'stop_name': stop['stop_name'],
                'stop_lat': stop['stop_lat'],
                'stop_lon': stop['stop_lon'],
                'gtfs_borough': stop['gtfs_borough'],
                'NTACode': '',
                'NTAName': 'UNMATCHED',
                'BoroName': '',
                'CountyFIPS': '',
            })
            unmatched += 1

    print(f"\nDone! {len(results)} stops processed, {unmatched} unmatched.")

    # Write output CSV
    out_path = os.path.join(base_dir, 'stops_with_nta.csv')
    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'gtfs_borough',
            'NTACode', 'NTAName', 'BoroName', 'CountyFIPS'
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"Output written to {out_path}")

    # Summary: stops per NTA
    from collections import Counter
    nta_counts = Counter(r['NTAName'] for r in results if r['NTAName'] != 'UNMATCHED')
    print(f"\n{'='*60}")
    print(f"SUMMARY: Bus stops per NTA (top 20)")
    print(f"{'='*60}")
    for nta, count in nta_counts.most_common(20):
        print(f"  {count:4d}  {nta}")
    print(f"  ...")
    print(f"  Total NTAs with bus stops: {len(nta_counts)}")
    print(f"  Unmatched stops: {unmatched}")


if __name__ == '__main__':
    main()