# %%
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
import polyline
import itertools
from tqdm import tqdm
import location
import networkx as nx
import visualize

# %%
pd.options.display.max_columns = 100

# %%
def generate_gtfs_routes():
    gtfs_bus_routes = []

    for company in ["flixbus", "alsa", "blabla"]:
        # for company in ["alsa"]:

        gtfspath = f"data/gtfs/bus/gtfs_{company}"

        stop_times = pd.read_csv(f"{gtfspath}/stop_times.txt", dtype={"stop_id": str})
        stops = pd.read_csv(f"{gtfspath}/stops.txt", dtype={"stop_id": str})
        trips = pd.read_csv(
            f"{gtfspath}/trips.txt", dtype={"trip_id": str, "route_id": str}
        )
        routes = pd.read_csv(
            f"{gtfspath}/routes.txt", dtype={"agency_id": str, "route_id": str}
        )
        agency = pd.read_csv(f"{gtfspath}/agency.txt", dtype={"agency_id": str})

        company_stops = (
            stop_times.merge(stops)
            .merge(trips)
            .merge(routes, on="route_id", suffixes=["_x", ""])
            .merge(agency)
            .sort_values(["trip_id", "stop_sequence"])[
                [
                    "agency_name",
                    "route_id",
                    "trip_id",
                    "stop_id",
                    "route_short_name",
                    "route_long_name",
                    "stop_sequence",
                    "stop_code",
                    "stop_name",
                    "arrival_time",
                    "departure_time",
                    "stop_lat",
                    "stop_lon",
                    "direction_id",
                ]
            ]
        )

        company_routes = company_stops.drop_duplicates(
            ["route_id", "stop_id", "direction_id"]
        )

        gtfs_bus_routes.append(company_routes)

    gtfs_bus_routes = pd.concat(gtfs_bus_routes, ignore_index=True)
    gtfs_bus_routes.to_parquet("data/bus_routes_gtfs.parquet", index=False)
    return gtfs_bus_routes


def process_gtfs_routes(gtfs_bus_routes, proj):
    x, y = proj(gtfs_bus_routes.stop_lon, gtfs_bus_routes.stop_lat)
    gtfs_bus_routes = gtfs_bus_routes.assign(stop_x=x / 1000, stop_y=y / 1000)
    return gtfs_bus_routes


def create_graph(gtfs_bus_routes):
    nodes = gtfs_bus_routes.drop_duplicates("stop_id").rename(
        columns=dict(
            stop_name="name",
            agency_name="agency",
            stop_lat="latitude",
            stop_lon="longitude",
        )
    )[["stop_id", "name", "latitude", "longitude", "agency"]]

    nodes_dict = nodes.set_index("stop_id").to_dict(orient="index")

    edges = pd.merge(
        gtfs_bus_routes[
            [
                "trip_id",
                "stop_id",
                "stop_sequence",
                "agency_name",
                "arrival_time",
                "departure_time",
            ]
        ].eval("next_stop_sequence=stop_sequence+1"),
        gtfs_bus_routes[["trip_id", "stop_id", "stop_sequence"]],
        left_on=["trip_id", "next_stop_sequence"],
        right_on=["trip_id", "stop_sequence"],
        how="left",
    )

    G = nx.from_pandas_edgelist(
        edges,
        source="stop_id_x",
        target="stop_id_y",
        edge_attr=["trip_id", "agency_name", "arrival_time", "departure_time"],
    )

    nx.set_node_attributes(G, nodes_dict)

    return G, edges, nodes


def create_routes(
    G: nx.Graph,
    gtfs_bus_routes: pd.DataFrame,
    city_pairs: pd.DataFrame,
):
    unique_bus_stops = gtfs_bus_routes.drop_duplicates("stop_id").reset_index(drop=True)

    x, y = proj(unique_bus_stops.stop_lon, unique_bus_stops.stop_lat)
    unique_bus_stops = unique_bus_stops.assign(
        stop_x=x / 1000,
        stop_y=y / 1000,
        stop_x_round=(x / 1000 / 10).round() * 10,
        stop_y_round=(y / 1000 / 10).round() * 10,
    )

    stop_kd_tree = cKDTree(unique_bus_stops[["stop_x", "stop_y"]].values)

    results = []

    for i, cp in tqdm(city_pairs.iterrows(), total=city_pairs.shape[0]):

        orig_pos = cp[["x0", "y0"]].to_list()
        dest_pos = cp[["x1", "y1"]].to_list()

        # query stops with in 10 km
        orig_bus_stop_idx = stop_kd_tree.query_ball_point(orig_pos, r=10)
        dest_bus_stop_idx = stop_kd_tree.query_ball_point(dest_pos, r=10)

        orig_stops = unique_bus_stops.loc[orig_bus_stop_idx]
        dest_stops = unique_bus_stops.loc[dest_bus_stop_idx]

        all_path_sets = [
            list(nx.all_shortest_paths(G, s, t))
            for s, t in itertools.product(
                orig_stops.stop_id.values, dest_stops.stop_id.values
            )
        ]
        path_sets = [
            path for paths in all_path_sets for path in paths if np.nan not in path
        ]

        for stops in path_sets:

            coordinates = [
                gtfs_bus_routes.query(f"stop_id=='{stop}'")
                .iloc[0][["stop_lon", "stop_lat"]]
                .values
                for stop in stops
            ]

            route_reconstruct = location.get_osm_route(coordinates)

            results.append(
                cp.to_dict()
                | dict(
                    stop_ids=stops,
                    duration=route_reconstruct["routes"][0]["duration"] / 60,
                    distance=route_reconstruct["routes"][0]["distance"] / 1000,
                    coords=polyline.encode(
                        [
                            (G.nodes[stop]["latitude"], G.nodes[stop]["longitude"])
                            for stop in stops
                        ]
                    ),
                    coords_full=route_reconstruct["routes"][0]["geometry"],
                )
            )

    bus_routes = pd.DataFrame.from_dict(results)
    return bus_routes


if __name__ == "__main__":
    # %%
    # gtfs_bus_routes = generate_gtfs_routes()
    gtfs_bus_routes = pd.read_parquet("data/bus_routes_gtfs.parquet")

    # %%
    city_pairs, proj = location.gen_city_pairs()
    G, edges, nodes = create_graph(gtfs_bus_routes)
    bus_routes = create_routes(G, gtfs_bus_routes, city_pairs)

    # %%
    bus_routes.to_parquet("data/bus_routes.parquet", index=False)

    # %%
    bus_routes = pd.read_parquet("data/bus_routes.parquet")

    # %%
    visualize.draw_sample_routes(bus_routes)
