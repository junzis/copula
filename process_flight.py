# %%
import pandas as pd
from tqdm import tqdm
from geopy.geocoders import Nominatim
from location import countries
import openap
import itertools

# %%
# Eurocontrol flight data


def process_ectl_data(file, fout=None):
    flights = (
        pd.read_csv(file)
        .rename(
            columns={
                "ICAO Flight Type": "scheduled",
                "FILED OFF BLOCK TIME": "fobt",
                "FILED ARRIVAL TIME": "fat",
                "ACTUAL OFF BLOCK TIME": "aobt",
                "ACTUAL ARRIVAL TIME": "aat",
                "STATFOR Market Segment": "market",
                "ADEP": "origin",
                "ADES": "destination",
                "ADEP Latitude": "lat0",
                "ADEP Longitude": "lon0",
                "ADES Latitude": "lat1",
                "ADES Longitude": "lon1",
                "AC Type": "typecode",
                "AC Operator": "operator",
                "ECTRL ID": "flight_id",
                "Actual Distance Flown (nm)": "distance_nm",
            }
        )
        .query("origin != destination")
        .drop(["AC Registration", "Requested FL"], axis=1)
        .assign(fobt=lambda x: pd.to_datetime(x.fobt, dayfirst=True))
        .assign(fat=lambda x: pd.to_datetime(x.fat, dayfirst=True))
        .assign(aobt=lambda x: pd.to_datetime(x.aobt, dayfirst=True))
        .assign(aat=lambda x: pd.to_datetime(x.aat, dayfirst=True))
        .assign(duration=lambda x: (x.fat - x.fobt).dt.total_seconds() / 60)
        .eval("distance=distance_nm * 1.852")
    )

    if fout is not None:
        flights.to_parquet(fout, index=False)

    return flights


# %%
file = "/mnt/8TB/ECTL_RD/2019/201903/Flights_20190301_20190331.csv.gz"
fout = "data/source/flight/flight_list_2019_03.parquet"
flights = process_ectl_data(file, fout=fout)

#%%
file = "data/source/flight/flight_list_2019_03.parquet"
flights = pd.read_parquet(file)

#%%
top_airports = (
    flights.groupby("origin")
    .agg({"flight_id": "count"})
    .sort_values("flight_id", ascending=False)
    .reset_index()
    .head(100)
)

airport_codes = top_airports.origin.values
airport_codes

#%%

# run following prompt in chatgpt-4, add save results as:
# data/source/flight/airport_info.csv

prompt = f"""
Your role is an assistant. No need to explain, just do the task.
Below is a list of airport code, give me a table include the following 
information for each airport: city located, closest big city, country, and iso country code.
Remember to present the result in csv format in a code block. 
The csv header columns should be: "airport","place","city","country","country_code"
Here is the list of airport codes: 
{airport_codes}
"""

print(prompt)


# %%


def gen_airport_dataset(fout=None):
    # airport information from chat-gpt
    airports = pd.read_csv("data/source/flight/airport_info.csv")
    airports = airports.query(f"country_code.isin({list(countries.keys())})")
    airports

    # load information for our_airports.org
    our_airport = pd.read_csv("data/source/flight/our_airports.csv")[
        ["ident", "type", "name", "latitude_deg", "longitude_deg", "iso_country"]
    ]
    our_airport = our_airport.rename(
        columns=dict(
            ident="airport",
            type="airport_type",
            latitude_deg="airport_latitude",
            longitude_deg="airport_longitude",
            iso_country="country_code",
        )
    )

    airports = airports.merge(our_airport)

    latitudes = []
    longitudes = []

    geolocator = Nominatim(user_agent="airports")

    for i, d in tqdm(airports.iterrows(), total=airports.shape[0]):
        location = geolocator.geocode(f"{d.city}, {d.country}")
        latitudes.append(location.latitude)
        longitudes.append(location.longitude)

    airports = airports.assign(city_latitude=latitudes, city_longitude=longitudes)

    if fout is not None:
        airports.to_csv(fout, index=False)

    return airports


#%%
# airports = gen_airport_dataset(fout="data/airports.csv")

airports = pd.read_csv("data/airports.csv")


# %%
# Eurocontrol flight data

n_days = flights.fobt.dt.date.nunique()

all_od_pairs = (
    flights.groupby(["origin", "destination"])
    .agg(
        {
            "distance": "mean",
            "duration": "mean",
            "flight_id": "count",
            "typecode": lambda x: pd.Series.mode(x)[0],  # most common ac type
        }
    )
    .reset_index()
    .assign(daily_flights=lambda x: x.flight_id / n_days)
    .drop("flight_id", axis=1)
)


# %%


def gen_flight_routes(airports):
    cities = airports.drop_duplicates(subset=["city"])

    # generate the all possible airport pairs
    city_pairs = pd.DataFrame(
        itertools.product(cities["city"], repeat=2),
        columns=["city_origin", "city_destination"],
    ).query("city_origin!=city_destination")

    flight_routes = (
        city_pairs.merge(airports, left_on=["city_origin"], right_on=["city"])
        .rename(columns={"airport": "origin"})
        .drop(columns=["city"])
        .merge(
            airports,
            left_on=["city_destination"],
            right_on=["city"],
            suffixes=("_origin", "_destination"),
        )
        .rename(columns={"airport": "destination"})
        .drop(columns=["city"])
    )

    # keep only pairs that have flight connections
    flight_routes = flight_routes.merge(all_od_pairs, how="inner")

    return flight_routes


#%%

flight_routes = gen_flight_routes(airports)

flight_routes.to_csv("data/flight_routes.csv", index=False)
