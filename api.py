#%%
from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import pandas as pd
import polyline
from geopy.distance import geodesic
import location
import emission
from shapely import LineString

#%%
app = FastAPI()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#%%
cities = pd.read_csv("data/airports.csv").drop_duplicates(subset=["city"])
flight_routes = pd.read_csv("data/flight_routes.csv")
car_routes = pd.read_parquet("data/car_routes.parquet")
bus_routes = pd.read_parquet("data/bus_routes.parquet")
train_routes = pd.read_parquet("data/train_routes.parquet")


#%%
def get_bearing(lat1, lon1, lat2, lon2):
    dLon = lon2 - lon1
    x = np.cos(np.radians(lat2)) * np.sin(np.radians(dLon))
    y = np.cos(np.radians(lat1)) * np.sin(np.radians(lat2)) - np.sin(
        np.radians(lat1)
    ) * np.cos(np.radians(lat2)) * np.cos(np.radians(dLon))
    bearing = np.arctan2(x, y)
    bearing = np.degrees(bearing)

    return bearing


#%%
@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.get("/cities")
def list_cities():
    return cities.city.sort_values().values.tolist()


@app.get("/destinations/{origin}")
def get_destinations(origin: str):
    return {
        "origin": cities.query("city==@origin")[
            ["city", "city_latitude", "city_longitude"]
        ].values.tolist(),
        "destination": cities.query("city!=@origin")[
            ["city", "city_latitude", "city_longitude"]
        ].values.tolist(),
    }


@app.get("/route/{origin}/{destination}")
def route(origin: str, destination: str):
    q = "city_origin==@origin and city_destination==@destination"

    flights = flight_routes.query(q)
    if flights.shape[0] == 0:
        flight_route = []
        flight_time = None
        flight_co2 = []
    else:
        flight = flights.iloc[0]
        flight_time = int(flight.duration)

        flight_emission = emission.Flight(flight.typecode)
        flight_co2 = flight_emission.co2(flight.distance)

        origin_coords = flight[["airport_latitude_origin", "airport_longitude_origin"]]
        destination_coords = flight[
            ["airport_latitude_destination", "airport_longitude_destination"]
        ]

        flight_route = []

        # Calculate great-circle path
        bearing = get_bearing(*origin_coords, *destination_coords)
        total_distance = geodesic(origin_coords, destination_coords).miles

        # Calculate points along the great-circle path
        for i in np.linspace(0, 1, 10):
            distance = i * total_distance
            point = geodesic(miles=distance).destination(origin_coords, bearing)
            flight_route.append((point.latitude, point.longitude))

    cars = car_routes.query(q)
    if cars.shape[0] == 0:
        car_route = []
        car_time = None
    else:
        car = cars.iloc[0]
        car_route = polyline.decode(car.coords)
        car_time = int(car.duration)

        car_emission = emission.Car("petrol")
        car_co2_2pax_petrol = car_emission.co2(car.distance)

        car_emission = emission.Car("diesel")
        car_co2_2pax_diesel = car_emission.co2(car.distance)

        car_emission = emission.Car("electric")
        car_co2_2pax_electric = car_emission.co2(
            car.distance, location.route_countries(car_route)
        )

    buses = bus_routes.query(q).sort_values("distance")
    if buses.shape[0] == 0:
        bus_route = []
        bus_time = None
        bus_co2 = []
    else:
        bus = buses.iloc[0]
        bus_route = polyline.decode(bus.coords)
        bus_time = int(bus.duration)

        bus_emission = emission.Bus()
        bus_co2 = bus_emission.co2(bus.distance)

    trains = train_routes.query(q)
    if trains.shape[0] == 0:
        train_route = []
        train_time = None
        train_co2 = []
    else:
        train = trains.iloc[0]
        train_route = polyline.decode(train.coords)
        train_time = int(train.duration)

        train_emission = emission.Train()
        train_co2 = train_emission.co2(
            train.distance, location.route_countries(train_route)
        )

    return {
        "routes": {
            "flight": {
                "route": flight_route,
                "info": f"CO2: {flight_co2} | Time: {flight_time} min",
            },
            "train": {"route": train_route, "info": ""},
            "bus": {"route": bus_route, "info": ""},
            "car": {"route": car_route, "info": ""},
        },
        "summary": [
            {"mode": "flight", "CO2": flight_co2, "Time": flight_time},
            {"mode": "train (electric)", "CO2": train_co2, "Time": train_time},
            {"mode": "bus", "CO2": bus_co2, "Time": bus_time},
            {"mode": "car (2p,diesel)", "CO2": car_co2_2pax_diesel, "Time": car_time},
            {"mode": "car (2p,petrol)", "CO2": car_co2_2pax_petrol, "Time": car_time},
            {
                "mode": "car(2p,electric)",
                "CO2": car_co2_2pax_electric,
                "Time": car_time,
            },
        ],
    }


#%%

origin = "Amsterdam"
destination = "Munich"

q = "city_origin==@origin and city_destination==@destination"

# flights = flight_routes.query(q)
# if flights.shape[0] == 0:
#     flight_route = []
# else:
#     # Calculate great-circle path
#     origin_coords = flights.iloc[0][
#         ["airport_latitude_origin", "airport_longitude_origin"]
#     ]
#     destination_coords = flights.iloc[0][
#         ["airport_latitude_destination", "airport_longitude_destination"]
#     ]

#     flight_route = []

#     # Calculate great-circle path
#     bearing = get_bearing(*origin_coords, *destination_coords)
#     total_distance = geodesic(origin_coords, destination_coords).miles

#     # Calculate points along the great-circle path
#     for i in np.linspace(0, 1, 10):
#         distance = i * total_distance
#         point = geodesic(miles=distance).destination(origin_coords, bearing)
#         flight_route.append((point.latitude, point.longitude))

# cars = car_routes.query(q)

# if cars.shape[0] == 0:
#     car_route = []
# else:
#     car_route = polyline.decode(cars.iloc[0].coords)

# car = cars.iloc[0]
# car_route = polyline.decode(car.coords)
# car_time = int(car.duration / 60)

# car_emission = emission.Car("petrol")
# car_co2 = car_emission.co2(car.distance, location.route_countries(car_route))

# car_co2 = f"{car_co2[0]} - {car_co2[1]} kg"

buses = bus_routes.query(q).sort_values("distance")
if buses.shape[0] == 0:
    bus_route = []
else:
    bus_route = polyline.decode(buses.iloc[0].coords)

# trains = train_routes.query(q)

# if trains.shape[0] == 0:
#     train_route = []
# else:
#     train_route = polyline.decode(trains.iloc[0].coords)

#%%

# %%
