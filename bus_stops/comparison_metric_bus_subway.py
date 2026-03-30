import pandas as pd
import numpy as np

# Load both datasets
bus = pd.read_csv('stops_with_nta.csv')
subway_nta = pd.read_csv('nta_subway_mapping/subway_stops_with_nta.csv')

# Count bus stops per NTA
bus_counts = bus.groupby('NTACode').agg(
    bus_stop_count=('stop_id', 'count'),
    NTAName=('NTAName', 'first'),
    BoroName=('BoroName', 'first')
).reset_index()

# Count subway stations per NTA
subway_counts = subway_nta.groupby('NTACode').agg(
    subway_station_count=('stop_id', 'count')
).reset_index()

# Full outer join so we capture NTAs with 0 subway stations
merged = bus_counts.merge(subway_counts, on='NTACode', how='left')
merged['subway_station_count'] = merged['subway_station_count'].fillna(0).astype(int)

print(f"Total NTAs with bus stops: {len(merged)}")
print(f"NTAs with 0 subway stations: {(merged['subway_station_count'] == 0).sum()}")
print(f"NTAs with subway stations: {(merged['subway_station_count'] > 0).sum()}")