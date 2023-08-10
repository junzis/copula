# %%
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
import polyline
import itertools
from tqdm import tqdm
import glob
import location
import heapq
import networkx as nx
import polyline
import visualize

# %%
pd.options.display.max_columns = 100

#%%
def gtfs_time_to_minutes(gtfs_time):
    """Convert GTFS time format to number of hour, can be > 24."""
    if isinstance(gtfs_time, str):
        H, M, S = map(int, gtfs_time.split(":"))
        minutes = H * 60 + M + S / 60
        return minutes
    else:
        return 0


def reformat_gtfs_time(gtfs_time):
    """Convert GTFS time format to standard time format."""
    if isinstance(gtfs_time, str):
        H, M, S = map(int, gtfs_time.split(":"))
        H %= 24
        return f"{H:02}:{M:02}:{S:02}"
    else:
        return None


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = (
        np.sin(delta_phi / 2) ** 2
        + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    )
    res = R * (2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a)))
    return np.round(res, 2)  # km


# %%
def generate_gtfs_routes():
    columns = [
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

    gtfs_routes = []

    for gtfspath in sorted(glob.glob("data/source/train/gtfs_*")):

        if ("germany_local" in gtfspath) or ("france_ter" in gtfspath):
            continue

        country = gtfspath.split("/")[-1]
        print(country)

        stop_times = pd.read_csv(
            f"{gtfspath}/stop_times.txt", dtype={"stop_id": str, "trip_id": str}
        )
        stops = pd.read_csv(f"{gtfspath}/stops.txt", dtype={"stop_id": str})
        trips = pd.read_csv(
            f"{gtfspath}/trips.txt", dtype={"trip_id": str, "route_id": str}
        )
        routes = pd.read_csv(
            f"{gtfspath}/routes.txt", dtype={"agency_id": str, "route_id": str}
        )
        calendar_dates = pd.read_csv(f"{gtfspath}/calendar_dates.txt")
        agency = pd.read_csv(f"{gtfspath}/agency.txt", dtype={"agency_id": str})

        # find a busy day  with most added service (or running services)
        if calendar_dates.query("exception_type==1").shape[0] > 0:
            date = (
                calendar_dates.query("exception_type==1")
                .groupby("date")
                .size()
                .sort_values(ascending=False)
                .reset_index()
                .iloc[0]
                .date
            )
        else:
            date = (
                calendar_dates.query("exception_type==2")
                .groupby("date")
                .size()
                .sort_values(ascending=True)
                .reset_index()
                .iloc[0]
                .date
            )

        service_running = calendar_dates.query(
            f"date==@date and exception_type==1"
        ).service_id.values

        service_removed = calendar_dates.query(
            f"date==@date and exception_type==2"
        ).service_id.values

        if calendar_dates.query("exception_type==2").shape[0] == 0:
            # exception_type is used as running services instead of added services
            trips_ = trips.query("service_id.isin(@service_running)")
        else:
            trips_ = trips.query(
                "service_id.isin(@service_running) or ~service_id.isin(@service_removed)"
            )

        df = (
            trips_.merge(routes)
            .merge(stop_times)
            .merge(stops)
            .merge(agency)
            .sort_values(["trip_id", "stop_sequence"])
        )

        if "finland" in gtfspath:
            df = df.query("agency_name.str.startswith('VR')")

        if "netherlands" in gtfspath:
            df = df.query("agency_id.str.startswith('IFF')")

        if "norway" in gtfspath:
            df = df.query(
                "agency_name.str.startswith('Vy') or agency_name.str.startswith('SJ')"
            )

        df = df[df.columns.intersection(columns)]

        if "direction_id" not in df.columns:
            df = df.assign(direction_id=np.nan)

        print(df.shape)

        gtfs_routes.append(df)

    gtfs_routes = pd.concat(gtfs_routes, ignore_index=True)

    gtfs_routes.to_parquet("data/train_routes_gtfs.parquet", index=False)

    return gtfs_routes


#%%
def process_gtfs_routes(gtfs_routes, proj):
    x, y = proj(gtfs_routes.stop_lon, gtfs_routes.stop_lat)
    gtfs_routes = gtfs_routes.assign(
        stop_x=x / 1000,
        stop_y=y / 1000,
        stop_x_round=(x / 1000 / 10).round() * 10,
        stop_y_round=(y / 1000 / 10).round() * 10,
    )

    # stops must be merges based on proximity!

    # merge stops that are close, < 1km apart, as the same stop
    unified_ids = (
        gtfs_routes.groupby(["stop_x_round", "stop_y_round"])
        .agg({"stop_name": lambda x: pd.Series.mode(x)[0]})
        .reset_index()
        .assign(uni_stop_id=lambda d: (d.index + 1).astype(str))
        .rename(columns=dict(stop_name="uni_stop_name"))
    )
    gtfs_routes = gtfs_routes.merge(unified_ids)

    return gtfs_routes


#%%
def create_graph(gtfs_routes):
    edges = pd.merge(
        gtfs_routes[
            [
                "agency_name",
                "trip_id",
                "stop_id",
                "uni_stop_id",
                "stop_sequence",
                "stop_name",
                "departure_time",
                "arrival_time",
                "stop_lat",
                "stop_lon",
            ]
        ].eval("next_stop_sequence=stop_sequence+1"),
        gtfs_routes[
            [
                "agency_name",
                "trip_id",
                "stop_id",
                "uni_stop_id",
                "stop_sequence",
                "stop_name",
                "departure_time",
                "arrival_time",
                "stop_lat",
                "stop_lon",
            ]
        ],
        left_on=["trip_id", "agency_name", "next_stop_sequence"],
        right_on=["trip_id", "agency_name", "stop_sequence"],
        how="left",
        suffixes=["_source", "_target"],
    ).assign(
        arrive_at_source_normal=lambda x: x.arrival_time_source.apply(
            reformat_gtfs_time
        ),
        arrive_at_source_mins=lambda x: x.arrival_time_source.apply(
            gtfs_time_to_minutes
        ),
        depart_from_target_normal=lambda x: x.departure_time_target.apply(
            reformat_gtfs_time
        ),
        depart_from_target_mins=lambda x: x.departure_time_target.apply(
            gtfs_time_to_minutes
        ),
        duration_mins=lambda x: (x.depart_from_target_mins - x.arrive_at_source_mins)
        % 1440,
    )

    nodes = gtfs_routes.drop_duplicates("uni_stop_id")[
        [
            "uni_stop_id",
            "uni_stop_name",
            "stop_name",
            "stop_lat",
            "stop_lon",
            "stop_x",
            "stop_y",
        ]
    ].reset_index(drop=True)

    nodes_dict = nodes.set_index("uni_stop_id").to_dict(orient="index")

    G = nx.from_pandas_edgelist(
        edges,
        source="uni_stop_id_source",
        target="uni_stop_id_target",
        edge_attr=[
            "trip_id",
            "stop_id_source",
            "stop_id_target",
            "agency_name",
            "arrive_at_source_mins",
            "depart_from_target_mins",
            "duration_mins",
            "stop_name_source",
            "arrival_time_source",
            "departure_time_source",
            "stop_lat_source",
            "stop_lon_source",
            "stop_name_target",
            "arrival_time_target",
            "departure_time_target",
            "stop_lat_target",
            "stop_lon_target",
        ],
        create_using=nx.MultiDiGraph,
    )

    nx.set_node_attributes(G, nodes_dict)

    invalid_nodes = [node for node in G.nodes if node != node]
    G.remove_nodes_from(invalid_nodes)

    return G, edges, nodes


#%%
def shortest_path(G, orig, dest):

    start_time = 360  # 6am

    if orig not in G or dest not in G:
        print("Invalid node(s)!")

    # Custom Dijkstra's algorithm to consider time constraints
    dist = {node: np.inf for node in G}
    prev = {node: {"node": None, "key": None, "data": None} for node in G}
    last_trip_id = {node: None for node in G}

    dist[orig] = start_time

    # cost of transferring
    transfer_penalty = 10

    # Increase to prioritize depart closer to start_time
    time_penalty_factor = 0.1

    # Priority queue: (distance, node)
    pq = [(start_time, orig)]
    visited = set()  # To keep track of visited nodes

    while pq:
        current_time, current_node = heapq.heappop(pq)

        # If the node has been visited before, skip
        if current_node in visited:
            continue
        else:
            visited.add(current_node)

        # Determine the "arrival time" at the current node.
        arrival_time_at_current = start_time if current_node == orig else current_time

        # Visit neighbors
        for me, neighbor, key, data in G.edges(current_node, data=True, keys=True):
            if arrival_time_at_current > data["depart_from_target_mins"]:
                continue

            time_penalty = (
                data["depart_from_target_mins"] - start_time
            ) * time_penalty_factor

            if (
                last_trip_id[current_node] is not None
                and last_trip_id[current_node] != data["trip_id"]
            ):
                penalty = transfer_penalty
            else:
                penalty = 0

            alt = current_time + data["duration_mins"] + penalty + time_penalty

            if alt < dist[neighbor]:
                dist[neighbor] = alt
                prev[neighbor] = {"node": current_node, "key": key, "data": data}
                last_trip_id[neighbor] = data["trip_id"]
                heapq.heappush(pq, (dist[neighbor], neighbor))

    # Reconstruct path with edges
    path_nodes = []
    path_edges = []
    stop = dest
    while stop is not None:
        path_nodes.insert(0, stop)
        if prev[stop]["node"] is not None:
            path_edges.insert(
                0, (prev[stop]["node"], stop, prev[stop]["key"], prev[stop]["data"])
            )
        stop = prev[stop]["node"]

    return path_nodes, path_edges


#%%
def create_train_routes(
    G: nx.Graph,
    nodes: pd.DataFrame,
    city_pairs: pd.DataFrame,
):

    stop_kd_tree = cKDTree(nodes[["stop_x", "stop_y"]].values)

    results = []

    for i, cp in tqdm(city_pairs.iterrows(), total=city_pairs.shape[0]):

        orig_pos = cp[["x0", "y0"]].to_list()
        dest_pos = cp[["x1", "y1"]].to_list()

        # query stops with in a range
        orig_train_stop_idx = stop_kd_tree.query_ball_point(orig_pos, r=5)
        dest_train_stop_idx = stop_kd_tree.query_ball_point(dest_pos, r=5)

        origs = nodes.loc[orig_train_stop_idx]
        dests = nodes.loc[dest_train_stop_idx]

        path_edges_set = []
        path_nodes_set = []
        travel_times = []
        for o, d in itertools.product(
            origs.uni_stop_id.values, dests.uni_stop_id.values
        ):
            path_nodes, path_edges = shortest_path(G, o, d)

            if len(path_edges) > 0:
                path_edges_set.append(path_edges)
                path_nodes_set.append(path_nodes)

                time_table = pd.DataFrame([pe[3] for pe in path_edges])[
                    ["arrive_at_source_mins", "depart_from_target_mins"]
                ].values
                travel_times.append(time_table[-1, 1] - time_table[0, 0])

        if len(travel_times) == 0:
            continue

        shortest_duration = min(travel_times)
        shortest_route = path_edges_set[np.argmin(travel_times)]

        df = pd.DataFrame([sr[3] for sr in shortest_route])

        df = df.assign(
            distance=lambda x: haversine(
                x.stop_lat_source,
                x.stop_lon_source,
                x.stop_lat_target,
                x.stop_lon_target,
            ),
        )

        # for stops in path_sets:
        results.append(
            cp.to_dict()
            | dict(
                duration=df.duration_mins.sum(),
                distance=df.distance.sum(),
                coords=polyline.encode(
                    np.append(
                        df[["stop_lat_source", "stop_lon_source"]].values,
                        df[["stop_lat_target", "stop_lon_target"]].iloc[-1:].values,
                        axis=0,
                    )
                ),
            )
        )

    train_routes = pd.DataFrame.from_dict(results)

    return train_routes


# %%
if __name__ == "__main__":
    city_pairs, proj = location.gen_city_pairs()

    #%%
    # gtfs_routes = generate_gtfs_routes()
    gtfs_routes = pd.read_parquet("data/train_routes_gtfs.parquet")

    #%%
    gtfs_routes = process_gtfs_routes(gtfs_routes, proj)

    #%%
    G, edges, nodes = create_graph(gtfs_routes)
    train_routes = create_train_routes(G, nodes, city_pairs)

    #%%
    train_routes.to_parquet("data/train_routes.parquet", index=False)

    # %%
    train_routes = pd.read_parquet("data/train_routes.parquet")

    # %%
    visualize.draw_sample_routes(train_routes)
