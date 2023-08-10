import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import polyline


def draw_coordinates(coords, margin=1.0):
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

    # Add the route to the map
    lats, lons = zip(*coords)
    ax.plot(lons, lats, color="blue", linewidth=2, transform=ccrs.Geodetic())

    # Add start and end points
    ax.scatter(
        coords[0][1],
        coords[0][0],
        color="tab:green",
        marker="o",
        transform=ccrs.Geodetic(),
        zorder=100,
    )
    ax.scatter(
        coords[-1][1],
        coords[-1][0],
        color="tab:red",
        marker="o",
        transform=ccrs.Geodetic(),
        zorder=100,
    )

    # Add features to the map
    ax.coastlines()
    ax.stock_img()

    # Set extent to cover the route with some margin
    min_lon, max_lon = np.min(lats), np.max(lats)
    min_lat, max_lat = np.min(lons), np.max(lons)
    ax.set_extent(
        [min_lat - margin, max_lat + margin, min_lon - margin, max_lon + margin],
        crs=ccrs.Geodetic(),
    )


def draw_route(route: pd.Series):
    draw_coordinates(np.array(polyline.decode(route.coords)))


def draw_sample_routes(routes: pd.DataFrame, sample=5):
    for i, route in (
        routes.drop_duplicates(["city_origin", "city_destination"])
        .sample(sample)
        .iterrows()
    ):
        draw_route(route)
