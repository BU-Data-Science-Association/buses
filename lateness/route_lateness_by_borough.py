import os
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


BOROUGH_GTFS_FOLDERS: Dict[str, str] = {
    "Brooklyn": "gtfs_b",
    "Bronx": "gtfs_bx",
    "Manhattan": "gtfs_m",
    "Queens": "gtfs_q",
    "Staten Island": "gtfs_si",
}


def parse_gtfs_time_to_seconds(value: str) -> float:
    """Parse GTFS HH:MM:SS time strings (HH can exceed 23)."""
    if pd.isna(value):
        return np.nan
    try:
        hh, mm, ss = str(value).split(":")
        return int(hh) * 3600 + int(mm) * 60 + int(ss)
    except Exception:
        return np.nan


def prepare_observed_segments(segment_speeds: pd.DataFrame) -> pd.DataFrame:
    required = [
        "Route ID",
        "Hour of Day",
        "Timepoint Stop ID",
        "Next Timepoint Stop ID",
        "Average Travel Time",
    ]
    missing = [c for c in required if c not in segment_speeds.columns]
    if missing:
        raise ValueError(f"segment_speeds is missing required columns: {missing}")

    observed = segment_speeds.copy()
    observed["stop_pair_id"] = (
        observed["Timepoint Stop ID"].astype(str)
        + "_"
        + observed["Next Timepoint Stop ID"].astype(str)
    )

    observed["Route ID"] = observed["Route ID"].astype(str).str.strip().str.upper()
    observed["Hour of Day"] = pd.to_numeric(observed["Hour of Day"], errors="coerce")
    observed = observed.dropna(subset=["Route ID", "Hour of Day", "stop_pair_id", "Average Travel Time"])
    observed["Hour of Day"] = observed["Hour of Day"].astype(int)

    # Keep granularity from segment_speeds rows so row counts can be used as weights later.
    observed["row_weight"] = 1.0
    return observed


def build_scheduled_segments_for_borough(gtfs_dir: str) -> pd.DataFrame:
    """Build scheduled timepoint-to-timepoint travel times by route/hour/stop pair."""
    stop_times_path = os.path.join(gtfs_dir, "stop_times.txt")
    stops_path = os.path.join(gtfs_dir, "stops.txt")
    trips_path = os.path.join(gtfs_dir, "trips.txt")

    stop_times = pd.read_csv(stop_times_path, dtype={"trip_id": str, "stop_id": str})
    stops = pd.read_csv(stops_path, usecols=["stop_id", "stop_name"], dtype={"stop_id": str})
    trips = pd.read_csv(trips_path, usecols=["trip_id", "route_id"], dtype={"trip_id": str, "route_id": str})

    if "timepoint" in stop_times.columns:
        stop_times = stop_times[stop_times["timepoint"] == 1].copy()
    else:
        stop_times = stop_times.copy()

    stop_times = stop_times.merge(trips, on="trip_id", how="left")
    stop_times = stop_times.dropna(subset=["route_id", "departure_time", "stop_sequence", "stop_id"])

    stop_times["dep_seconds"] = stop_times["departure_time"].apply(parse_gtfs_time_to_seconds)
    stop_times = stop_times.dropna(subset=["dep_seconds"])

    stop_times["route_id"] = stop_times["route_id"].astype(str).str.strip().str.upper()
    stop_times["dep_hour"] = (stop_times["dep_seconds"] // 3600).astype(int) % 24

    stop_times = stop_times.merge(stops, on="stop_id", how="left")

    tp = stop_times.sort_values(["trip_id", "route_id", "stop_sequence"]).copy()
    tp["next_stop_id"] = tp.groupby(["trip_id", "route_id"])["stop_id"].shift(-1)
    tp["next_stop_name"] = tp.groupby(["trip_id", "route_id"])["stop_name"].shift(-1)
    tp["next_dep_seconds"] = tp.groupby(["trip_id", "route_id"])["dep_seconds"].shift(-1)

    tp = tp.dropna(subset=["next_stop_id", "next_dep_seconds"])
    tp["travel_time_min"] = (tp["next_dep_seconds"] - tp["dep_seconds"]) / 60.0
    tp = tp[tp["travel_time_min"] > 0].copy()

    tp["stop_pair_id"] = tp["stop_id"].astype(str) + "_" + tp["next_stop_id"].astype(str)
    tp["stop_pair"] = tp["stop_name"].fillna("") + " - " + tp["next_stop_name"].fillna("")

    scheduled = (
        tp.groupby(["route_id", "dep_hour", "stop_pair_id", "stop_pair"], as_index=False)
        .agg(
            scheduled_avg_min=("travel_time_min", "mean"),
            scheduled_trip_count=("travel_time_min", "count"),
        )
        .rename(columns={"dep_hour": "hour"})
    )
    return scheduled


def compute_borough_lateness(observed: pd.DataFrame, gtfs_dir: str, borough_name: str) -> pd.DataFrame:
    """
    Compute route-level weighted lateness for one borough.

    Weighting inside a borough uses the count of matched observed segment rows.
    """
    print("Building scheduled segments for borough:", borough_name)
    scheduled = build_scheduled_segments_for_borough(gtfs_dir)
    print(f"Built scheduled segments for {borough_name}: {len(scheduled)} rows")
    merged = observed.merge(
        scheduled,
        left_on=["Route ID", "Hour of Day", "stop_pair_id"],
        right_on=["route_id", "hour", "stop_pair_id"],
        how="inner",
    )

    if merged.empty:
        print(f"No matches found for {borough_name}")
        return pd.DataFrame(
            columns=[
                "borough",
                "route_id",
                "weighted_avg_lateness_min",
                "weight",
                "matched_rows",
                "matched_unique_segments",
            ]
        )

    merged["lateness_min"] = merged["Average Travel Time"] - merged["scheduled_avg_min"]

    by_route = (
        merged.groupby("Route ID", as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "weighted_avg_lateness_min": np.average(g["lateness_min"], weights=g["row_weight"]),
                    "weight": g["row_weight"].sum(),
                    "matched_rows": len(g),
                    "matched_unique_segments": g[["Hour of Day", "stop_pair_id"]].drop_duplicates().shape[0],
                }
            )
        )
        .rename(columns={"Route ID": "route_id"})
    )
    print(f"{borough_name}: Computed lateness for {len(by_route)} routes")
    by_route["borough"] = borough_name
    by_route = by_route[
        [
            "borough",
            "route_id",
            "weighted_avg_lateness_min",
            "weight",
            "matched_rows",
            "matched_unique_segments",
        ]
    ]
    return by_route


def combine_borough_results(borough_results: Iterable[pd.DataFrame]) -> pd.DataFrame:
    per_borough = pd.concat(list(borough_results), ignore_index=True)
    if per_borough.empty:
        return pd.DataFrame(columns=["route_id", "weighted_avg_lateness_min", "total_weight", "boroughs_present"])

    overall = (
        per_borough.groupby("route_id", as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "weighted_avg_lateness_min": np.average(
                        g["weighted_avg_lateness_min"],
                        weights=g["weight"],
                    ),
                    "total_weight": g["weight"].sum(),
                    "boroughs_present": g["borough"].nunique(),
                }
            )
        )
        .sort_values("weighted_avg_lateness_min", ascending=False)
    )
    return overall


def run_all_boroughs(
    segment_speeds_path: str,
    data_root: str,
    borough_folders: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    print("Reading observed segment speeds from:", segment_speeds_path)
    observed_raw = pd.read_csv(segment_speeds_path)
    observed = prepare_observed_segments(observed_raw)

    folders = borough_folders or BOROUGH_GTFS_FOLDERS

    per_borough_results: List[pd.DataFrame] = []
    for borough_name, folder in folders.items():
        gtfs_dir = os.path.join(data_root, folder)
        if not os.path.exists(gtfs_dir):
            print(f"Skipping {borough_name}: missing folder {gtfs_dir}")
            continue
        print("Running for borough:", borough_name)

        result = compute_borough_lateness(observed=observed, gtfs_dir=gtfs_dir, borough_name=borough_name)
        per_borough_results.append(result)
        print(
            f"{borough_name}: {len(result)} routes with matches, "
            f"{int(result['matched_rows'].sum()) if not result.empty else 0} matched rows"
        )

    per_borough = pd.concat(per_borough_results, ignore_index=True) if per_borough_results else pd.DataFrame()
    overall = combine_borough_results(per_borough_results)

    return per_borough, overall


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)

    segment_speeds_path = os.path.join(project_root, "segment_speeds.csv")
    data_root = os.path.join(base_dir, "data")

    per_borough, overall = run_all_boroughs(
        segment_speeds_path=segment_speeds_path,
        data_root=data_root,
    )

    out_per_borough = os.path.join(base_dir, "route_lateness_by_borough.csv")
    out_overall = os.path.join(base_dir, "route_weighted_lateness_overall.csv")

    per_borough.to_csv(out_per_borough, index=False)
    overall.to_csv(out_overall, index=False)

    print(f"Wrote per-borough route lateness: {out_per_borough}")
    print(f"Wrote overall weighted route lateness: {out_overall}")


if __name__ == "__main__":
    main()
