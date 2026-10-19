from pathlib import Path
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import geopandas as gpd

BOUNDARIES = "ne_50m_admin_0_countries.geojson"
Path("output").mkdir(exist_ok=True)

#attribute table 
fc = pd.read_csv("data/forecasts.csv", parse_dates=["date"]).sort_values(["country", "date"])
g = fc.groupby("country")["rate"]
fc["index_100"] = fc["rate"] / g.transform("first") * 100    
fc["yoy_pct"] = g.pct_change(12) * 100 
fc["pct_change_mom"] = g.pct_change() * 100
fc["status"] = np.where(fc["is_forecast"], "Forecast", "Historical")
fc["is_forecast"] = fc["is_forecast"].astype(int)
fc = fc.rename(columns={"rate": "lcu_per_usd", "lower": "lcu_lower95", "upper": "lcu_upper95"})

fc["yoy_pct_clip"] = fc["yoy_pct"].clip(-50, 100)

world = gpd.read_file(BOUNDARIES)
world["iso3"] = np.where(world["ISO_A3_EH"].isin(["-99", None]), world["ADM0_A3"], world["ISO_A3_EH"])
world["iso3"] = world["iso3"].replace({"KOS": "XKX"})
world["geometry"] = world.geometry.simplify(0.05, preserve_topology=True)

n_before = len(world)
world = (world.assign(_area=world.geometry.area).sort_values("_area", ascending=False)
              .drop_duplicates("iso3").drop(columns="_area"))
if n_before != len(world):
    print(f"Ignored {n_before - len(world)} extra polygon(s) that share a country code (e.g. AUS dependencies)")
world = world[["iso3", "NAME", "geometry"]].rename(columns={"NAME": "map_name"})

unmatched = sorted(set(fc["iso3"]) - set(world["iso3"]))
print(f"{fc['iso3'].nunique() - len(unmatched)} / {fc['iso3'].nunique()} countries matched to a polygon")
print("No polygon for:", unmatched)

def fmt_rate(x):
    return f"{x:,.0f}" if x >= 1000 else f"{x:,.1f}" if x >= 100 else f"{x:,.2f}"

layer = world.merge(fc, on="iso3", how="inner")
layer["date"] = pd.to_datetime(layer["date"])
layer["month"] = layer["date"].dt.strftime("%Y-%m")         
layer["date"] = layer["date"] + pd.Timedelta(days=14, hours=12)
rate_txt = layer["lcu_per_usd"].map(fmt_rate)
layer["label"] = layer["map_name"] + "\n" + rate_txt + np.where(layer["is_forecast"] == 1, "\nforecast", "")
layer["label_short"] = layer["iso3"] + " " + rate_txt
layer = gpd.GeoDataFrame(layer, geometry="geometry", crs="EPSG:4326")
layer.to_file("output/exchange_rates_temporal.gpkg", layer="exchange_rates", driver="GPKG")

print(f"Saved {len(layer)} features ({layer['date'].nunique()} months) -> output/exchange_rates_temporal.gpkg")
print(layer.dtypes[["date", "yoy_pct", "status"]])
