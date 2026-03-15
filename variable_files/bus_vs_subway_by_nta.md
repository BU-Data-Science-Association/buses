# Bus vs Subway by NTA

## Overview

This CSV quantifies how dependent each NYC Neighborhood Tabulation Area (NTA) is on bus service relative to subway access. It is one component of the **Bus Need Index**, which measures which neighborhoods would benefit most from a fare-free bus system.

## Columns

| Column | Description |
|---|---|
| `NTACode` | Unique NTA identifier (e.g. `BX0702`) |
| `NTAName` | Human-readable neighborhood name |
| `bus_stop_count` | Total number of bus stops in the NTA |
| `subway_station_count` | Total number of subway stations in the NTA |
| `bus_dependency_ratio` | Value from 0–1 representing bus dependency (see below) |

## Bus Dependency Ratio

```
bus_dependency_ratio = bus_stop_count / (bus_stop_count + subway_station_count)
```

- **1.0** — No subway stations at all; the NTA relies entirely on buses. 85 of 215 NTAs fall here, concentrated in Staten Island, eastern Queens, and outer Brooklyn.
- **~0.5** — Roughly equal bus and subway presence; lowest bus dependency.
- Values in between scale proportionally.

This ratio was chosen over a raw difference (bus stops minus subway stations) because it is already normalized to [0, 1] and can plug directly into the Bus Need Index without additional scaling. It is also size-invariant — a large NTA with many stops of both types is compared fairly against a small one.

## How Subway Stations Were Mapped to NTAs

The subway GTFS `stops.txt` was filtered to parent stations only (`location_type = 1`), yielding 496 unique stations. Each station was assigned to the NTA of its **nearest bus stop** using Euclidean distance on latitude/longitude. This is a reliable proxy because bus stops densely cover every NTA (mean distance to nearest bus stop ≈ 220 m).

## Data Sources

- **Bus stops → NTA**: `stops_with_nta.csv` (pre-existing project file, 11,536 stops across 215 NTAs)
- **Subway stations**: MTA GTFS `stops.txt` (496 parent stations)
- **NTA definitions**: [NYC DCP Neighborhood Tabulation Areas](https://www.nyc.gov/content/planning/pages/resources/datasets/neighborhood-tabulation)
