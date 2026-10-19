import os, warnings, itertools
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.statespace.sarimax import SARIMAX

warnings.filterwarnings("ignore")
HORIZON = 12
SEASONAL = (0, 1, 1, 12)

ALLOW_NAIVE_AS_FINAL = False

COUNTRIES = ["IND", "CHN", "JPN", "GBR", "DEU", "BRA", "RUS", "CAN", "AUS", "KOR",
            "MEX", "IDN", "TUR", "ZAF", "NGA", "ARG", "EGY", "CHE", "THA", "PAK"]

df = pd.read_csv("data/exchange_rate_long.csv", parse_dates=["date"])

def choose_d(y):
    try:
        return 0 if adfuller(y, autolag="AIC")[1] < 0.05 else 1
    except Exception:
        return 1

def fit(y, order, seasonal=(0, 0, 0, 0)):
    trend = "c" if order[1] == 0 and seasonal[1] == 0 else "n"
    return SARIMAX(y, order=order, seasonal_order=seasonal, trend=trend,
                enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=100)

def best_order(y, d):
    best, best_aic = (1, d, 1), np.inf
    for p, q in itertools.product(range(3), range(3)):
        try:
            aic = fit(y, (p, d, q)).aic
            if aic < best_aic:
                best, best_aic = (p, d, q), aic
        except Exception:
            continue
    return best

def rmse(a, b): return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))
def mape(a, b): return float(np.mean(np.abs((np.asarray(a) - np.asarray(b)) / np.asarray(a))) * 100)

def process(country, iso3, g):
    warnings.simplefilter("ignore")
    g = g.sort_values("date")
    dates, rate = g["date"].values, g["rate"].values
    y = pd.Series(np.log(rate), index=pd.DatetimeIndex(dates, freq="MS"))
    future_idx = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=HORIZON, freq="MS")

    hist = pd.DataFrame({"country": country, "iso3": iso3, "date": y.index, "rate": rate,
                        "is_forecast": False, "model": "actual"})

    if np.ptp(rate) < 1e-9 * abs(rate[0]):
        fc = pd.DataFrame({"country": country, "iso3": iso3, "date": future_idx, "rate": rate[-1],
                           "lower": rate[-1], "upper": rate[-1], "is_forecast": True, "model": "constant"})
        met = dict(country=country, iso3=iso3, order="-", best_model="constant", d=0,
                   naive_rmse=0, naive_mape=0, arima_rmse=np.nan, arima_mape=np.nan,
                   sarima_rmse=np.nan, sarima_mape=np.nan)
        return pd.concat([hist, fc]), met

    train, test = y.iloc[:-HORIZON], y.iloc[-HORIZON:]
    actual = np.exp(test.values)
    d = choose_d(train)
    order = best_order(train, d)

    scores = {"naive": (rmse(actual, np.exp(np.repeat(train.iloc[-1], HORIZON))),
                        mape(actual, np.exp(np.repeat(train.iloc[-1], HORIZON))))}
    for name, seas in (("arima", (0, 0, 0, 0)), ("sarima", SEASONAL)):
        try:
            pred = np.exp(fit(train, order, seas).forecast(HORIZON).values)
            scores[name] = (rmse(actual, pred), mape(actual, pred))
        except Exception:
            scores[name] = (np.nan, np.nan)

    cands = [k for k in scores if not np.isnan(scores[k][1]) and (ALLOW_NAIVE_AS_FINAL or k != "naive")]
    best = min(cands, key=lambda k: scores[k][1]) if cands else "naive"


    if best == "naive":
        mu = np.repeat(y.iloc[-1], HORIZON); lo = hi = mu
        sd = y.diff().dropna().std() * np.sqrt(np.arange(1, HORIZON + 1))
        lo, hi = mu - 1.96 * sd, mu + 1.96 * sd
    else:
        res = fit(y, order, SEASONAL if best == "sarima" else (0, 0, 0, 0))
        f = res.get_forecast(HORIZON)
        mu = f.predicted_mean.values
        ci = f.conf_int(alpha=0.05).values
        lo, hi = ci[:, 0], ci[:, 1]
    fc = pd.DataFrame({"country": country, "iso3": iso3, "date": future_idx, "rate": np.exp(mu),
                       "lower": np.exp(lo), "upper": np.exp(hi), "is_forecast": True, "model": best})
    met = dict(country=country, iso3=iso3, order=str(order), best_model=best, d=d,
               naive_rmse=scores["naive"][0], naive_mape=scores["naive"][1],
               arima_rmse=scores["arima"][0], arima_mape=scores["arima"][1],
               sarima_rmse=scores["sarima"][0], sarima_mape=scores["sarima"][1])
    return pd.concat([hist, fc]), met

if __name__ == "__main__":
    os.environ["PYTHONWARNINGS"] = "ignore" 
    groups = [(c, g["iso3"].iloc[0], g) for c, g in df.groupby("country")
              if COUNTRIES is None or g["iso3"].iloc[0] in COUNTRIES]
    missing = [c for c in (COUNTRIES or []) if c not in {a[1] for a in groups}]
    if missing:
        print("Not found in data (dropped in preprocessing?):", missing)
    print(f"Fitting ARIMA / SARIMA for {len(groups)} countries (a few minutes)...")
    out = []
    gen = Parallel(n_jobs=-1, return_as="generator")(delayed(process)(*a) for a in groups)
    for i, res in enumerate(gen, 1):
        out.append(res)
        print(f"\r  progress: {i}/{len(groups)}", end="", flush=True)
    print()
    fcst = pd.concat([o[0] for o in out], ignore_index=True)
    metrics = pd.DataFrame([o[1] for o in out])

    fcst.to_csv("data/forecasts.csv", index=False)
    metrics.to_csv("data/model_metrics.csv", index=False)

    print("\nBest model counts:\n", metrics["best_model"].value_counts().to_string())
    print("\nMedian holdout MAPE (%):")
    print(metrics[["arima_mape", "sarima_mape"]].median().round(2).to_string())
