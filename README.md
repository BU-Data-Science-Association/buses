# NYC Bus Need Index

A data-driven analysis measuring which New York City neighborhoods would benefit most from improved bus service. The **Bus Need Index** scores all 215 Neighborhood Tabulation Areas (NTAs) across NYC on a 0–1 scale, synthesizing income, car dependency, subway access, bus reliability, and ridership data into a single composite metric — visualized through an interactive web map.

This project earned a presentation slot at the NYC School of Data Conference after winning a popular vote among attendees.

We also have a **blog post** accompanying this project with a deeper narrative walkthrough of our findings and methodology.

Check out our interactive map here: https://busneedmap.netlify.app/

---

## Team

Built by the **BU Data Science Association (BUDSA)**:

- Sam Cowan
- Hassan Dawy
- Sophia Ye
- Rayan Khan
- Gina Lim

---

## Project Motivation

New York City's bus network is the largest in North America, yet many neighborhoods — particularly in the outer boroughs — suffer from unreliable service, long headways, and limited subway alternatives. We set out to answer: **which neighborhoods need bus improvements the most, and why?**

The Bus Need Index provides a quantitative, reproducible answer by combining publicly available transit, demographic, and economic data into a single score per neighborhood.

---

## How the Index Works

Each NTA receives five normalized component scores (0–1), which are combined into a weighted sum to produce a final index score from 0 (lowest need) to 1 (highest need).

### Component Scores

| Component | Weight | What It Measures | Direction |
|-----------|--------|-----------------|-----------|
| **Income** | 0.25 | Median household income (Census B19013) | Lower income → higher score |
| **Car Usage** | 0.20 | % of residents commuting by car | Lower car use → higher score |
| **Bus vs Subway** | 0.20 | Ratio of bus stops to total transit stops | More bus-dependent → higher score |
| **Reliability** | 0.15 | Weighted average bus lateness by route | Worse reliability → higher score |
| **Ridership** | 0.20 | Average ridership across routes serving the NTA | Higher ridership → higher score |


## Interactive Map

The project includes a self-contained interactive web map built with **Leaflet.js**:

- **Choropleth visualization** of Bus Need Index across all 215 NTAs (green → yellow → red)
- **Hover tooltips** showing each NTA's score breakdown across all 5 components
- **Adjustable weights** — sliders let users change component weights and see the map update in real time
- **Bus route overlay** — toggle priority and secondary routes based on how many high-need NTAs they serve
- **Threshold slider** — define "high-need" as the top X% of NTAs to dynamically reclassify routes
- **Statistics panel** — live mean, min, max scores and a ranked top-10 list

### Running the Map Locally

```bash
cd map
python -m http.server 8000
```

Then open `http://localhost:8000/index.html` in your browser.

---

## Repository Structure

```
buses/
├── README.md
├── LICENSE                              # MIT License
│
├── bus_stops/                           # Geospatial bus/subway stop assignments
│   ├── stops_to_nta.py                  # Maps 11,500+ bus stops to NTAs via point-in-polygon
│   ├── comparison_metric_bus_subway.py  # Computes bus dependency ratio per NTA
│   ├── data/
│   │   ├── gtfs_b/, gtfs_bx/, gtfs_m/, gtfs_q/, gtfs_si/   # MTA GTFS feeds (5 boroughs)
│   │   ├── gtfs_subway/                 # Subway GTFS data
│   │   └── nynta2020_26a/              # NYC NTA shapefile (EPSG:2263)
│   └── subway_stops/
│       └── subway_nta_mapping.py        # Maps subway stations to NTAs
│
├── income_by_nta/                       # Income component
│   ├── income_by_nta.ipynb              # Census tract income → NTA-level income score
│   ├── tract_income.csv                 # Census B19013 median household income
│   └── tract_nta_crosswalk.csv          # Census tract → NTA mapping
│
├── lateness/                            # Bus speed & lateness analysis
│   ├── buses.ipynb                      # Segment-level speed EDA and scheduled vs actual comparison
│   └── route_lateness_by_borough.py     # Computes weighted lateness per route per borough
│
├── merge_datasets/                      # Central index calculation
│   ├── merge_datasets.ipynb             # Combines all 5 scores → final Bus Need Index
│   ├── bus_need_index_final.csv         # Output: NTACode + final score (for the map)
│   ├── bus_need_index_final_full.csv    # Output: all component scores + final index
│   ├── route_nta_mapping.csv            # Route-to-NTA crosswalk
│   ├── weighted_lateness_*.csv          # Bus lateness data by borough
│   └── MTA_Bus_Route_Averages_Clean.csv # Ridership data by route
│
├── demographic_insights/                # Validation & analysis
│   ├── demographic_insights.ipynb       # Correlates index with poverty, SNAP, unemployment
│   ├── env_analysis.ipynb               # Air quality analysis by NTA
│   └── nta_demographics_clean.csv       # Demographic variables per NTA
│
├── election_analysis/                   # Election correlation analysis
│   ├── election_correlation.py          # Correlation with 2025 mayoral election results
│   └── nta_mayoral_results_2025_general.csv # Election data by NTA
│
├── nta_map/                                 # Interactive web map
│   ├── index.html                       # Leaflet.js map application
│   ├── get_routes.ipynb                 # Generates bus route GeoJSON
│   ├── bus_need_index_final.csv         # Score data consumed by the map
│   ├── component_scores.json            # Per-NTA score breakdown for tooltips
│   ├── nynta2020.geojson                # NTA boundary polygons
│   └── bus_routes.geojson               # Bus routes classified by priority
│
└── variable_files/                      # Documentation
    └── bus_vs_subway_by_nta.md          # Methodology explanation for bus/subway metric
```

---

## Data Sources

| Source | Data Used |
|--------|-----------|
| **MTA GTFS Feeds** | Bus stops, subway stations, routes, trips, schedules |
| **US Census Bureau (ACS B19013)** | Median household income by census tract |
| **NYC Dept. of City Planning** | NTA boundary shapefiles (2020 vintage) |
| **MTA Performance Data** | Bus lateness (weighted by segment speed), average ridership by route |
| **NYC Open Data** | Vehicle commuting patterns, demographic snapshots, election results |

---

## Validation

We validated the index against independent demographic and political data:

- **Poverty rate** — moderate positive correlation with Bus Need Index (Pearson r ≈ 0.35–0.45, p < 0.001)
- **SNAP recipient rate** — similar positive correlation, confirming higher-need NTAs are economically disadvantaged
- **2025 Mayoral election** — tested correlation between index scores and vote share for transit-focused candidates

---

## Technologies

- **Python** — Pandas, NumPy, SciPy, Matplotlib, Seaborn
- **Geospatial** — Custom shapefile parsing with point-in-polygon (ray casting), coordinate transforms (WGS84 ↔ NAD83 State Plane)
- **Web** — Leaflet.js, CartoDB basemap tiles, vanilla JavaScript
- **Data formats** — GTFS, GeoJSON, Shapefile, CSV

---

## License

MIT License — © 2026 BU Data Science Association. See [LICENSE](LICENSE) for details.
