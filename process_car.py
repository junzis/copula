# %%
import pandas as pd
from tqdm import tqdm
import location
import visualize
import shapely
import polyline

# %%
if __name__ == "__main__":
    city_pairs, proj = location.gen_city_pairs()

    # %%
    route_list = []

    for i, cp in tqdm(city_pairs.iterrows(), total=city_pairs.shape[0]):
        route = location.get_osm_route([(cp.lon0, cp.lat0), (cp.lon1, cp.lat1)])

        coords_simplified = (
            shapely.LineString(polyline.decode(route["routes"][0]["geometry"]))
            .simplify(tolerance=0.01)
            .coords
        )

        route_list.append(
            dict(
                index=i,
                duration=route["routes"][0]["duration"] / 60,  # -> minutes
                distance=route["routes"][0]["distance"] / 1000,  # -> km
                coords=polyline.encode(coords_simplified),
            )
        )

    car_routes = city_pairs.merge(
        pd.DataFrame(route_list).set_index("index"), left_index=True, right_index=True
    )

    #%%
    car_routes.to_parquet("data/car_routes.parquet", index=False)

    # %%
    car_routes = pd.read_parquet("data/car_routes.parquet")

    #%%
    visualize.draw_sample_routes(car_routes)
