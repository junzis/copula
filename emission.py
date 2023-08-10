#%%
from dataclasses import dataclass
import openap
from openap import polymer

#%%
# gram per kWh
co2_kwh = {
    "EU-27": 238.0,
    "Austria": 82.0,
    "Belgium": 139.0,
    "Bulgaria": 398.0,
    "Croatia": 138.0,
    "Cyprus": 605.0,
    "Czechia": 397.0,
    "Denmark": 123.0,
    "Estonia": 656.0,
    "Finland": 70.0,
    "France": 58.0,
    "Germany": 348.0,
    "Greece": 397.0,
    "Hungary": 188.0,
    "Ireland": 332.0,
    "Italy": 234.0,
    "Latvia": 106.0,
    "Lithuania": 127.0,
    "Luxembourg": 45.0,
    "Malta": 349.0,
    "Netherlands": 339.0,
    "Poland": 721.0,
    "Portugal": 167.0,
    "Romania": 212.0,
    "Slovakia": 113.0,
    "Slovenia": 211.0,
    "Spain": 165.0,
    "Sweden": 9.0,
}

# https://www.kaggle.com/datasets/debajyotipodder/co2-emission-by-vehicles
# https://ev-database.org/cheatsheet/energy-consumption-electric-car

car_co2 = {
    "diesel": {
        "co2_km_low": 200,  # gram co2
        "co2_km_high": 270,
    },
    "petrol": {
        "co2_km_low": 210,
        "co2_km_high": 280,
    },
    "electric": {
        "kwh_km_low": 0.15,
        "kwh_km_high": 0.25,
    },
}


#%%
class Flight:
    def __init__(self, typecode):
        self.typecode = typecode
        self.poly = polymer.Flight(typecode)

        ac = openap.prop.aircraft(typecode)
        self.mass = ac["limits"]["MTOW"] * 0.9
        self.pax_low, self.pax_high = ac["pax"]["low"], ac["pax"]["high"]

    def co2(self, distance):
        co2_low = self.poly.co2(distance=distance, mass=self.mass) / self.pax_high
        co2_high = self.poly.co2(distance=distance, mass=self.mass) / self.pax_low
        return int(round(co2_low[0], -1)), int(round(co2_high[0], -1))


class Train:
    def __init__(self):
        self.kWh_pax_km_low = 0.03
        self.kWh_pax_km_high = 0.05

    def co2(self, distance: float, countries: dict):
        co2_kg_kWh = 0
        for country, fraction in countries.items():
            co2_kg_kWh_country = co2_kwh.get(country, co2_kwh["EU-27"]) / 1000
            co2_kg_kWh += co2_kg_kWh_country * fraction

        co2_low = self.kWh_pax_km_low * co2_kg_kWh * distance
        co2_high = self.kWh_pax_km_high * co2_kg_kWh * distance

        return round(co2_low), round(co2_high)


class Bus:
    def __init__(self):
        self.co2_pax_km_low = 0.03
        self.co2_pax_km_high = 0.08

    def co2(self, distance: float):
        co2_low = self.co2_pax_km_low * distance
        co2_high = self.co2_pax_km_high * distance

        return round(co2_low), round(co2_high)


class Car:
    def __init__(self, car_type):
        self.car_type = car_type

    def co2(self, distance: float, countries: dict = None):
        if self.car_type in ["petrol", "diesel"]:
            co2_km = car_co2[self.car_type]
            co2_low = co2_km["co2_km_low"] / 1000 * distance
            co2_high = co2_km["co2_km_high"] / 1000 * distance
            return round(co2_low), round(co2_high)

        elif self.car_type == "electric":
            assert countries is not None

            car_co2_kwh = car_co2[self.car_type]
            co2_kg_kWh = 0
            for country, fraction in countries.items():
                co2_kg_kWh_country = co2_kwh.get(country, co2_kwh["EU-27"]) / 1000
                co2_kg_kWh += co2_kg_kWh_country * fraction

            co2_low = car_co2_kwh["kwh_km_low"] * co2_kg_kWh * distance
            co2_high = car_co2_kwh["kwh_km_high"] * co2_kg_kWh * distance

            return round(co2_low), round(co2_high)


# Sample instantiation of each class
# flight = Flight(typecode="A320")
# flight.co2(3000)
# sample_train = Train(train_type="high-speed", country="France")
# sample_bus = Bus()
# sample_car = Car(car_type="diesel")
# sample_flight, sample_train, sample_bus, sample_car
