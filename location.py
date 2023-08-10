import pandas as pd
import itertools
from pyproj import Proj, Geod
from shapely.geometry import Point, LineString
import geopandas as gpd

countries = {
    "AL": "Albania",
    "AT": "Austria",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CH": "Switzerland",
    "CZ": "Czech Republic",
    "DE": "Germany",
    "DK": "Denmark",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IT": "Italy",
    "LU": "Luxembourg",
    "ME": "Montenegro",
    "MK": "Macedonia",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Republic of Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "XK": "Kosovo",
}

world = gpd.read_parquet("data/naturalearth_lowres.parquet")


def gen_city_pairs(airports: pd.DataFrame = None):

    if airports is None:
        airports = pd.read_csv("data/airports.csv")

    city_pairs = pd.DataFrame(
        itertools.product(airports["city"].unique(), repeat=2),
        columns=["city_origin", "city_destination"],
    ).query("city_origin!=city_destination")

    city_pairs = (
        city_pairs.merge(
            airports[["city", "city_latitude", "city_longitude"]],
            left_on="city_origin",
            right_on="city",
        )
        .merge(
            airports[["city", "city_latitude", "city_longitude"]],
            left_on="city_destination",
            right_on="city",
        )
        .drop(columns=["city_x", "city_y"])
        .rename(
            columns=dict(
                city_latitude_x="lat0",
                city_longitude_x="lon0",
                city_latitude_y="lat1",
                city_longitude_y="lon1",
            )
        )
        .drop_duplicates(["city_origin", "city_destination"])
    )

    proj = Proj(
        proj="lcc",
        ellps="WGS84",
        lat_1=city_pairs.lat0.min(),
        lat_2=city_pairs.lat0.max(),
        lat_0=city_pairs.lat0.mean(),
        lon_0=city_pairs.lon0.mean(),
    )

    x0, y0 = proj(city_pairs.lon0, city_pairs.lat0)
    x1, y1 = proj(city_pairs.lon1, city_pairs.lat1)

    city_pairs = city_pairs.assign(
        x0=x0 / 1000, x1=x1 / 1000, y0=y0 / 1000, y1=y1 / 1000
    )

    return city_pairs, proj


def get_osm_route(lonlats, server_url="http://router.project-osrm.org"):
    import requests

    lonlats_str = ";".join([f"{c[0]},{c[1]}" for c in lonlats])

    osrm_url = f"{server_url}/route/v1/driving"

    response = requests.get(f"{osrm_url}/{lonlats_str}?overview=full")
    route = response.json()

    return route


def route_countries(coords_lonlat):

    coords = [Point((lat, lon)) for lon, lat in coords_lonlat]
    route_ = LineString(coords)

    gdf_route = gpd.GeoDataFrame(geometry=coords)
    gdf_route.crs = "EPSG:4326"
    countries = set(gpd.sjoin(gdf_route, world, predicate="within")["ADMIN"])

    coutires = {}

    geod = Geod(ellps="WGS84")

    total_distance = geod.geometry_length(route_)

    for i, country in world.query("ADMIN.isin(@countries)").iterrows():
        intersection = route_.intersection(country.geometry)
        distance = geod.geometry_length(intersection)
        coutires[country["ADMIN"]] = round(distance / total_distance, 2)

    return coutires
