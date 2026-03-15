import pandas as pd
import numpy as np

# Load subway stops - filter to parent stations only (location_type=1)
subway = pd.read_csv('../data/gtfs_subway/stops.txt')
subway_stations = subway[subway['location_type'] == 1].copy()
print(f"Total subway rows: {len(subway)}")
print(f"Parent stations (location_type=1): {len(subway_stations)}")
print(subway_stations.head())

# Load bus stops with NTA
bus = pd.read_csv('../stops_with_nta.csv')
print(f"\nBus stops with NTA: {len(bus)}")
print(f"Unique NTAs in bus data: {bus['NTACode'].nunique()}")

# For each subway station, find the nearest bus stop and assign that NTA
bus_lats = bus['stop_lat'].values
bus_lons = bus['stop_lon'].values
bus_nta_codes = bus['NTACode'].values
bus_nta_names = bus['NTAName'].values
bus_boro_names = bus['BoroName'].values

results = []
for _, row in subway_stations.iterrows():
    slat, slon = row['stop_lat'], row['stop_lon']
    # Haversine-like distance (approximate, fine for small distances in NYC)
    dlat = bus_lats - slat
    dlon = bus_lons - slon
    dist = np.sqrt(dlat**2 + (dlon * np.cos(np.radians(slat)))**2)
    nearest_idx = np.argmin(dist)
    
    results.append({
        'stop_id': row['stop_id'],
        'stop_name': row['stop_name'],
        'stop_lat': row['stop_lat'],
        'stop_lon': row['stop_lon'],
        'NTACode': bus_nta_codes[nearest_idx],
        'NTAName': bus_nta_names[nearest_idx],
        'BoroName': bus_boro_names[nearest_idx],
        'nearest_bus_stop_dist_deg': dist[nearest_idx]
    })

subway_nta = pd.DataFrame(results)
print(f"\nSubway stations mapped to NTAs: {len(subway_nta)}")
print(f"Max distance to nearest bus stop (degrees): {subway_nta['nearest_bus_stop_dist_deg'].max():.6f}")
print(f"Mean distance: {subway_nta['nearest_bus_stop_dist_deg'].mean():.6f}")
print(f"\nSample output:")
print(subway_nta.head(10))

# Save subway to NTA mapping
subway_nta.to_csv('../subway_stops_with_nta.csv', index=False)
print("\nSaved subway_stops_with_nta.csv")

# Borough distribution
print("\nSubway stations per borough:")
print(subway_nta['BoroName'].value_counts())