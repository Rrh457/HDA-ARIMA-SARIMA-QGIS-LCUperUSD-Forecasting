# Project Guide: Global Exchange Rates - Spatial-Temporal Analysis with ARIMA / SARIMA

*Everything you need to explain this project to your teacher without having to read the code line by line.*
Read sections 1-3 first (10 minutes), then skim 12 (Q&A) before the demo.

---

## Table of contents
1. [The 30-second pitch](#1-the-30-second-pitch)
2. [What the project is and why](#2-what-the-project-is-and-why)
3. [Big picture: the pipeline](#3-big-picture-the-pipeline)
4. [The input data (the xlsx)](#4-the-input-data-the-xlsx)
5. [Script 1: `01_preprocess.py` (pandas)](#5-script-1-01_preprocesspy-pandas)
6. [Script 2: `02_forecast.py` (ARIMA / SARIMA)](#6-script-2-02_forecastpy-arima--sarima)
7. [Script 3: `03_build_qgis_layer.py` (GeoPandas)](#7-script-3-03_build_qgis_layerpy-geopandas)
8. [QGIS: styling and the Temporal Controller](#8-qgis-styling-and-the-temporal-controller)
9. [Our actual results](#9-our-actual-results)
10. [Limitations (be honest about these)](#10-limitations-be-honest-about-these)
11. [How to run it + troubleshooting](#11-how-to-run-it--troubleshooting)
12. [Teacher Q&A cheat sheet](#12-teacher-qa-cheat-sheet)
13. [Glossary](#13-glossary)
14. [Suggested demo flow (5 minutes)](#14-suggested-demo-flow-5-minutes)

---

## 1. The 30-second pitch

> "We took World Bank monthly exchange rates (local currency per US dollar) for ~200 countries from 2015 to Sept 2026. We cleaned and reshaped them with **pandas**, then fitted **ARIMA and SARIMA** time-series models to forecast the next 12 months for 20 major economies, checking each model on a 12-month test period. Finally we joined the results to a world map in **QGIS** and animated them month by month with the **Temporal Controller**, so you can watch currencies strengthen or weaken over time and into the forecast."

Three technologies: **pandas** (preprocessing), **ARIMA/SARIMA** (forecasting), **QGIS** (visualisation).

---

## 2. What the project is and why

**Topic from the brief:** global economic temporal and spatial analysis with ARIMA/SARIMA forecasting.
The brief lists five indicators (exchange rate, inflation, industrial production, exports, imports). **We implemented the exchange-rate indicator**, which is the file we have. The same pipeline works for the other indicators if the same kind of file is provided, because nothing in the code is specific to exchange rates except column naming.

**Temporal** = changes over time (monthly series, forecasts).
**Spatial** = changes across places (countries on a map).
So the project answers: *how do exchange rates move over time, what might happen next, and which parts of the world are seeing the biggest moves?*

---

## 3. Big picture: the pipeline

```
Official_exchange_rate__LCU_per_USD__period_average.xlsx   (original, never modified)
        |
        |  01_preprocess.py  (pandas)
        v
data/exchange_rate_long.csv        data/preprocess_report.csv
        |
        |  02_forecast.py  (statsmodels: ARIMA / SARIMA)
        v
data/forecasts.csv                 data/model_metrics.csv
        |
        |  03_build_qgis_layer.py  (GeoPandas + Natural Earth boundaries)
        v
output/exchange_rates_temporal.gpkg
        |
        |  QGIS  (graduated choropleth + Temporal Controller)
        v
Animated map of exchange-rate change, history + forecast
```

| File | What it is |
|---|---|
| `Official_exchange_rate__LCU_per_USD__period_average.xlsx` | The original World Bank data. **Read only; never edited.** |
| `01_preprocess.py` | Cleans and reshapes the data |
| `02_forecast.py` | Fits ARIMA/SARIMA, tests them, forecasts 12 months |
| `03_build_qgis_layer.py` | Joins the numbers to country shapes and saves a QGIS file |
| `ne_50m_admin_0_countries.geojson` | Natural Earth country boundaries (the map shapes) |
| `data/*.csv` | Intermediate results (so each step can be inspected in Excel) |
| `data/forecasts_all188.csv`, `model_metrics_all188.csv` | The same results for all 188 countries (kept as a backup) |
| `output/exchange_rates_temporal.gpkg` | The final layer loaded into QGIS |

---

## 4. The input data (the xlsx)

**Source:** World Bank Global Economic Monitor (GEM). The indicator is **"Official exchange rate, LCU per USD, period average"**.

- **LCU** = Local Currency Unit (rupee, yen, peso...). A value of 94.7 for India means **1 US dollar = 94.7 rupees**.
- **Period average** = the average rate over the month (not the last day of the month).
- **Higher number = the local currency is weaker** against the dollar (you need more of it to buy 1 USD).

**Layout of the file**
- Two sheets: `annual` and `monthly`. **We only use `monthly`.**
- `monthly` has one row per month (labels like `2015M03` = March 2015), from **1996M10 to 2026M09** (360 months).
- One **column per country** (199 countries). Row 1 holds the country names, and row 2 is blank.
- This is called **"wide" format** (countries are spread across columns). Analysis tools prefer **"long" format** (one row per country-month), which is why script 1 reshapes it.

**Why 2015 onwards?** The project brief asks for 2015 to the latest available month. That gives 141 months (Jan 2015 - Sep 2026).

---

## 5. Script 1: `01_preprocess.py` (pandas)

**Goal:** turn the messy wide Excel sheet into a clean, tidy table that the forecasting code and the map can use.

### What it does, step by step

| Step | What happens | Why |
|---|---|---|
| 1. Read | `pd.read_excel(..., sheet_name="monthly")` | Load the monthly sheet |
| 2. Remove junk row | Keep only rows whose label matches `YYYYMmm` (a regular expression) | The blank 2nd row would otherwise become bad data |
| 3. Parse dates | `2015M03` becomes the real date `2015-03-01` | Time-series tools need real dates |
| 4. Numeric conversion | `pd.to_numeric(errors="coerce")` | Any odd text becomes NaN (missing) instead of crashing |
| 5. Filter | Keep only 2015-01-01 onwards | Matches the brief |
| 6. Missing-data rule | See below | Models can't work with holes |
| 7. ISO3 codes | Map names to 3-letter codes | Needed to join to the map |
| 8. Reshape | `melt` converts wide to long | One row per country-month |
| 9. Derived columns | `pct_change_mom`, `yoy_pct`, `index_100` | Raw rates can't be compared across countries |
| 10. Save | `exchange_rate_long.csv` and `preprocess_report.csv` | Hand-off to the next step |

### The missing-data rule
- If a country has **more than 12 missing months** since 2015 (or is entirely empty), it is **dropped**.
- Otherwise small **gaps in the middle are linearly interpolated** (a straight line between the neighbouring known values).
- A few missing months at the very start or end are filled by copying the nearest value (`ffill`/`bfill`).
- **11 countries dropped:** Afghanistan, Greenland, Liberia, Myanmar, Mauritania, Sudan, Somalia, Syria, Turkmenistan, Venezuela, US Virgin Islands.
- **188 countries kept.** `data/preprocess_report.csv` lists every decision.

### ISO3 codes
The World Bank file uses names ("Egypt, Arab Rep.", "Korea, Rep.") but the map file uses codes. ISO3 is the international 3-letter country code (India = IND, Japan = JPN). We use the `pycountry` library for most names plus a manual dictionary (`NAME_FIX`) for names it can't resolve, such as "Venezuela, RB" or "Lao, PDR". The script prints a warning if any name has no code.

### Columns in `data/exchange_rate_long.csv`

| Column | Meaning | How it is calculated | Example (India) |
|---|---|---|---|
| `country` | Country name (World Bank spelling) | from the xlsx header | India |
| `iso3` | 3-letter country code | name lookup | IND |
| `date` | First day of the month | `2015M01` becomes 2015-01-01 | 2016-01-01 |
| `rate` | Local currency units per 1 USD, monthly average | straight from the xlsx (after gap filling) | 67.31 |
| `pct_change_mom` | % change from the previous month | `(rate_t / rate_t-1 - 1) x 100` | 1.16 |
| `yoy_pct` | % change vs the same month a year earlier ("year on year") | `(rate_t / rate_t-12 - 1) x 100` | 8.22 |
| `index_100` | Rate relative to Jan 2015, where Jan 2015 = 100 | `rate_t / rate_Jan2015 x 100` | 108.22 |

**How to read them:**
- Positive `pct_change_mom` or `yoy_pct` = the currency **weakened** vs the USD (more local currency needed per dollar). Negative = it **strengthened**.
- `index_100 = 152` (India, Sep 2026) means the dollar costs 52% more rupees than in January 2015.
- `yoy_pct` is empty for all of 2015 because there is no earlier year to compare with, so colours start in January 2016.
- **Why derive these at all?** Raw rates are not comparable: INR is about 90 per USD while IDR is about 16,000 per USD. Percent changes and an index put every country on the same scale, and that is what we map.

---

## 6. Script 2: `02_forecast.py` (ARIMA / SARIMA)

**Goal:** for each chosen country, predict the next 12 months of exchange rate and measure how trustworthy the model is.

### 6.1 Concepts you should be able to explain

**Time series.** A list of values over time (here: one rate per month). The idea of forecasting is that the past values carry information about the next ones.

**Stationarity.** A series is stationary if its average and spread don't drift over time. Exchange rates usually trend (India's rupee keeps weakening), so they are *not* stationary. ARIMA models need stationary data.

**Differencing.** Replacing each value with the change from the previous month. This removes trends and makes the series stationary. The `d` in ARIMA is how many times we difference (almost always 0 or 1).

**ADF test (Augmented Dickey-Fuller).** A statistical test for stationarity. If its p-value is below 0.05, we treat the series as already stationary (d = 0). Otherwise we difference once (d = 1). In the code: `choose_d()`.

**ARIMA(p, d, q).** Three building blocks:
- **AR(p) = AutoRegressive:** the next value depends on the previous `p` values.
- **I(d) = Integrated:** the data was differenced `d` times to remove the trend.
- **MA(q) = Moving Average:** the next value depends on the previous `q` forecasting errors (shocks).

Example: India's best order was **(1, 1, 0)**: difference once, use one past value, no error terms.

**SARIMA(p, d, q)(P, D, Q, m).** ARIMA plus a **seasonal** part for patterns that repeat every `m` steps. With monthly data, `m = 12` (a yearly cycle, like "always rises in December"). We use seasonal order **(0, 1, 1, 12)**, i.e. one seasonal difference (compare each month with the same month last year) plus one seasonal moving-average term. The non-seasonal (p, d, q) is the same one found for ARIMA.

**ARIMA vs SARIMA in one line:** SARIMA = ARIMA + "does the pattern repeat every year?". For exchange rates, seasonality is usually weak, so SARIMA sometimes helps (India, Japan) and sometimes hurts (Egypt, Nigeria).

**Both are used in the project:** every country gets both an ARIMA and a SARIMA model, and the better one is used for the forecast.

**AIC (Akaike Information Criterion).** A score for how well a model fits the data while penalising complexity. **Lower is better.** We use it to choose between candidate (p, q) combinations without overfitting.

**Log transform.** The models work on `log(rate)` instead of the raw rate. It stabilises big swings and turns "changes" into percentage-like changes, so countries with very different currency sizes behave similarly. Forecasts are converted back with `exp()`.

**Naive forecast (benchmark).** "Next month's rate = this month's rate." No maths, no model. Exchange rates behave much like a random walk, so this simple guess is hard to beat. We compute its error too, as a **yardstick**: a fancy model is only worth it if it beats the naive guess. *It is not the Spearman correlation or anything statistical; it's just a repeat of the last value.*

### 6.2 What the code does for each country

1. **Take the country's series** and convert to `log(rate)` with a proper monthly date index.
2. **Check for a constant series** (e.g. a hard peg where the rate never changes). If constant, skip modelling and carry the last value forward (`model = "constant"`).
3. **Split into train and test.** Train = everything except the last 12 months. Test = the last 12 months (Oct 2025 - Sep 2026). The model never sees the test months while being fitted.
4. **Choose `d`** with the ADF test on the training data.
5. **Choose `(p, q)`.** Try every combination of p in {0,1,2} and q in {0,1,2} (9 models) and keep the one with the lowest AIC.
6. **Fit ARIMA** with that order on the training data, forecast the 12 test months, compare with the real values.
7. **Fit SARIMA** (same order + seasonal (0,1,1,12)), forecast the same 12 months, compare.
8. **Fit the naive benchmark** and compare too.
9. **Score each** with RMSE and MAPE (below).
10. **Pick the winner between ARIMA and SARIMA** (lowest MAPE). Naive is *not* eligible as the final model unless `ALLOW_NAIVE_AS_FINAL = True`.
11. **Refit the winner on ALL the data** (including the test months) and forecast the **next 12 months** (Oct 2026 - Sep 2027), with a 95% interval.
12. **Save** the history + forecast rows and the scores.

All countries are processed in parallel (`joblib`) to save time. Python warnings are silenced so the terminal stays clean, and a one-line progress counter is shown.

### 6.3 The error measures

Both compare predicted vs actual rates over the 12 test months, on the original (not log) scale.

- **RMSE** = Root Mean Squared Error = `sqrt(average of (actual - predicted)^2)`. In the currency's own units (e.g. rupees per dollar). Penalises large misses. *Can't be compared across countries* because currencies have different sizes.
- **MAPE** = Mean Absolute Percentage Error = `average of |actual - predicted| / actual x 100`. "On average the forecast was off by x%". **This is the one to quote and to compare across countries.**

Rule of thumb for exchange rates: under 5% is good, 5-10% is okay, higher means a shock or an unstable currency.

### 6.4 The 95% interval
A forecast is a best guess, not a certainty. The `lower` and `upper` columns give a range that, under the model's assumptions, should contain the true value about 95% of the time. **It widens the further ahead we look**, because uncertainty accumulates. (Calculated on the log scale, then converted back, so the band is slightly asymmetric.) We did *not* check empirically how often reality falls inside it.

### 6.5 Columns in `data/forecasts.csv`
One row per country per month: history (Jan 2015 - Sep 2026) plus 12 forecast months.

| Column | Meaning |
|---|---|
| `country`, `iso3` | Country name and code |
| `date` | Month (first day) |
| `rate` | History: the real rate. Forecast rows: the predicted rate |
| `is_forecast` | `False` = real data, `True` = predicted |
| `model` | `actual` for real data; `arima`, `sarima` or `constant` for forecast rows (the model that produced them) |
| `lower`, `upper` | 95% interval for forecast rows (empty for real data) |

### 6.6 Columns in `data/model_metrics.csv`
One row per country.

| Column | Meaning |
|---|---|
| `order` | The chosen (p, d, q), e.g. (1, 1, 0) |
| `best_model` | Which model made the final forecast: `arima`, `sarima` or `constant` |
| `d` | Differencing order from the ADF test |
| `naive_rmse`, `naive_mape` | Error of the "repeat last value" benchmark |
| `arima_rmse`, `arima_mape` | Error of ARIMA on the 12-month test |
| `sarima_rmse`, `sarima_mape` | Error of SARIMA on the 12-month test |

### 6.7 Settings at the top of the file
| Setting | Default | Effect |
|---|---|---|
| `HORIZON` | 12 | Months to forecast and months held out for testing |
| `SEASONAL` | (0, 1, 1, 12) | The seasonal part of SARIMA |
| `ALLOW_NAIVE_AS_FINAL` | False | If True, naive can be chosen as the final model when it scores best |
| `COUNTRIES` | list of 20 ISO3 codes | Which countries to model. `None` = all 188 (~3 min) |

---

## 7. Script 3: `03_build_qgis_layer.py` (GeoPandas)

**Goal:** attach the numbers to country shapes and save one file QGIS can animate.

1. **Load `forecasts.csv`** and compute the map columns (`index_100`, `yoy_pct`, `pct_change_mom`) again, this time over history **and** forecast months so the forecast months can be coloured too.
2. **Load the country shapes** from Natural Earth (`ne_50m_admin_0_countries.geojson`: vector polygons, 1:50 million scale). Match to our data by ISO3 (Kosovo is fixed from `KOS` to `XKX`).
3. **Simplify the shapes** (`simplify(0.05)`, about 5 km tolerance). Each country's polygon is repeated for every month, so full detail would make the file huge (236 MB for all countries). Simplified, it is far smaller and QGIS stays fast.
4. **Join** (merge) the table to the shapes. Result: **one feature (row) per country per month**, each with the country's polygon attached.
5. **Save as a GeoPackage** (`.gpkg`, an open spatial database format) in CRS EPSG:4326 (standard longitude/latitude, WGS84). The `date` column is a real DateTime field, which the Temporal Controller needs.

With 20 countries x 153 months (141 history + 12 forecast) there are **3,366 features**.

### Columns in the QGIS layer

| Column | Meaning | Where it comes from |
|---|---|---|
| `iso3` | Country code | join key |
| `map_name` | Country name as spelt in Natural Earth | boundary file |
| `country` | Country name as spelt by the World Bank | forecasts.csv |
| `date` | Month, as a DateTime (drives the animation) | forecasts.csv |
| `lcu_per_usd` | Exchange rate (real or forecast) | `rate` renamed |
| `lcu_lower95`, `lcu_upper95` | 95% interval (forecast months only) | `lower`, `upper` renamed |
| `is_forecast` | 0 = history, 1 = forecast | converted from True/False |
| `status` | Text label: "Historical" or "Forecast" | from `is_forecast`; handy for filtering and styling |
| `model` | `actual`, `arima`, `sarima`, `constant` | forecasts.csv |
| `index_100` | Rate relative to Jan 2015 = 100 | recalculated |
| `pct_change_mom` | Month-on-month % change | recalculated |
| `yoy_pct` | 12-month % change | recalculated |
| `yoy_pct_clip` | `yoy_pct` capped to between -50 and +100 | **used for the colours only** |
| `geometry` | The country polygon | Natural Earth |

**Why `yoy_pct_clip`?** A few currencies (Argentina, Turkey) move by hundreds of percent. If we colour with raw values, one extreme country stretches the scale and everyone else looks the same. Capping the value at -50 / +100 for colouring keeps the map readable. The true values stay in `yoy_pct` and show in the attribute table.

---

## 8. QGIS: styling and the Temporal Controller

### Load
Layer > Add Layer > Add Vector Layer > `output/exchange_rates_temporal.gpkg` (layer `exchange_rates`). Optionally add a plain world-boundaries layer underneath so non-modelled countries show as grey context.

### Symbology (the choropleth)
- **Choropleth** = a map where regions are coloured by a value.
- Layer Properties > **Symbology** > **Graduated**.
- **Value:** `yoy_pct_clip`. **Mode:** Equal Count (Quantile), **5 classes**, then press **Classify**.
- **Colour ramp:** RdYlGn, **inverted**, so red = currency weakened vs USD and green = strengthened.
- Quantile mode puts roughly the same number of features in each colour class.

### Temporal Controller (the animation)
- Layer Properties > **Temporal** > tick *Dynamic Temporal Control* > Configuration: **Single Field with Date/Time** > Field: **`date`** > event duration = 1 month.
- View > Panels > **Temporal Controller** > choose *Animated*, set the range to the full range (2015-01 to 2027-09), step = **1 month**, press play.
- At each step QGIS shows only the features whose `date` falls in that month, so the map updates month by month. Forecast months (Oct 2026 onwards) show automatically at the end.
- To mark forecast months visibly, add a second copy of the layer filtered with `"status" = 'Forecast'` and give it a hatched or outlined style.

---

## 9. Our actual results

Run on data up to September 2026. The holdout is Oct 2025 - Sep 2026. Your run may differ slightly (a different statsmodels version can converge slightly differently).

| Country | ISO3 | Order (p,d,q) | Final model | Naive MAPE % | ARIMA MAPE % | SARIMA MAPE % |
|---|---|---|---|---|---|---|
| Argentina | ARG | (1, 1, 2) | SARIMA | 3.04 | 42.94 | 31.41 |
| Australia | AUS | (1, 1, 0) | ARIMA | 5.36 | 5.03 | 5.19 |
| Brazil | BRA | (0, 1, 1) | ARIMA | 3.46 | 3.22 | 4.92 |
| Canada | CAN | (1, 0, 1) | SARIMA | 0.90 | 2.56 | 1.93 |
| China | CHN | (1, 1, 0) | SARIMA | 3.43 | 2.95 | 2.74 |
| Egypt, Arab Rep. | EGY | (1, 1, 0) | ARIMA | 4.35 | 4.38 | 11.33 |
| Germany | DEU | (1, 1, 0) | ARIMA | 1.08 | 1.37 | 1.56 |
| India | IND | (1, 1, 0) | SARIMA | 4.60 | 4.46 | 3.30 |
| Indonesia | IDN | (2, 1, 0) | SARIMA | 4.02 | 4.21 | 2.58 |
| Japan | JPN | (1, 1, 0) | SARIMA | 6.12 | 6.05 | 4.12 |
| Korea, Rep. | KOR | (2, 1, 2) | SARIMA | 4.85 | 5.78 | 5.16 |
| Mexico | MEX | (1, 0, 1) | ARIMA | 5.13 | 7.17 | 7.21 |
| Nigeria | NGA | (1, 1, 1) | ARIMA | 8.40 | 8.34 | 18.48 |
| Pakistan | PAK | (1, 1, 0) | ARIMA | 1.16 | 1.05 | 5.25 |
| Russian Federation | RUS | (1, 1, 0) | ARIMA | 6.08 | 6.50 | 7.05 |
| South Africa | ZAF | (1, 1, 0) | ARIMA | 5.50 | 5.03 | 6.10 |
| Switzerland | CHE | (0, 1, 1) | ARIMA | 1.16 | 1.21 | 1.56 |
| Thailand | THA | (1, 1, 0) | ARIMA | 2.13 | 2.41 | 2.44 |
| Turkey | TUR | (1, 1, 2) | SARIMA | 7.58 | 8.74 | 7.21 |
| United Kingdom | GBR | (1, 1, 0) | ARIMA | 0.82 | 0.92 | 1.03 |

**Median MAPE across the 20 countries:** naive = 4.19%, ARIMA = 4.42%, SARIMA = 5.04%.
Final model counts: ARIMA 12, SARIMA 8.

**What to take from this**
- All three methods are in the same ballpark (around 4-5% median error).
- SARIMA clearly helped for **India (4.6% -> 3.3%)**, **Japan (6.1% -> 4.1%)**, **Indonesia (4.0% -> 2.6%)** and **China (3.4% -> 2.7%)**.
- For stable currencies (UK, Germany, Switzerland, Canada) the naive guess is already very good, and nothing beats it by much.
- **Argentina** is the outlier: a currency crisis inside the test window makes ARIMA and SARIMA miss by 31-43%. The naive guess was far better (3%), but it isn't allowed as the final model, so the map uses SARIMA for Argentina. That is a good example to discuss honestly.
- **Egypt and Nigeria:** SARIMA was bad (11% and 18%), so ARIMA was chosen automatically for them.

---

## 10. Limitations (be honest about these)

1. **Model selection uses the same test set it is scored on.** Choosing the winner on the 12-month test and then reporting that score makes it slightly optimistic. A stricter method is rolling-origin cross-validation (several test windows).
2. **A single 12-month test window.** One unusual year (Argentina, Turkey) can dominate a country's score.
3. **Narrow model search.** p and q are limited to 0-2 and d to 0-1, with the seasonal part fixed to (0,1,1,12). We did not test whether exchange rates are seasonal.
4. **Warnings are hidden.** Some fits did not fully converge (`ConvergenceWarning` in statsmodels). We silenced them to keep the terminal tidy. We did not run residual checks (Ljung-Box).
5. **Intervals not validated.** We have not checked whether about 95% of real values really fall inside the 95% bands.
6. **Exchange rates are close to a random walk,** so long forecasts have inherently low accuracy. Treat the forecasts as projections with uncertainty, not predictions of fact.
7. **Gap filling is an approximation.** Interpolated or copied months are not real observations.
8. **11 countries were excluded** for too much missing data (Venezuela, Myanmar, Sudan and others).
9. **Only the exchange-rate indicator is covered,** not the other four from the brief.
10. **Eurozone countries share one currency,** so modelling several of them would repeat the same series. We use Germany to represent the euro area.
11. **Map simplification** may erase or distort very small countries, and some tiny states are not visible at world scale.

---

## 11. How to run it + troubleshooting

Install once:
```
pip install pandas openpyxl pycountry statsmodels joblib geopandas pyogrio
```
Run these **one per line, with no comments after them** (Windows Command Prompt treats `>` in a comment as "redirect output", which causes "The system cannot find the path specified"):
```
python 01_preprocess.py
python 02_forecast.py
python 03_build_qgis_layer.py
```
Keep all files in one folder: the three scripts, the xlsx, and `ne_50m_admin_0_countries.geojson`.

| Problem | Fix |
|---|---|
| "The system cannot find the path specified" | You pasted a `# comment` with `->` in it. Run the commands without comments. |
| `FileNotFoundError` for the xlsx | The xlsx must be in the same folder you run the command from, with the exact file name. |
| `ModuleNotFoundError` | Run the `pip install` line above. |
| Terminal flooded with warnings | Use the latest `02_forecast.py` (warnings are silenced inside the worker processes). |
| Script 2 looks frozen | It only updates the progress counter after each country finishes. Wait for `Best model counts`. Don't press Ctrl+C. |
| `KeyboardInterrupt` | You pressed Ctrl+C. Run the script again. |
| QGIS map is empty after play | Check Temporal tab > *Dynamic Temporal Control* is ticked and the field is `date`. |
| Map is all one colour | Make sure the value is `yoy_pct_clip` (not `yoy_pct`) and you pressed Classify. |
| Colours missing for 2015 | Expected: `yoy_pct` needs 12 months of history, so colours start in Jan 2016. |

---

## 12. Teacher Q&A cheat sheet

**Q: What data did you use?**
A: World Bank GEM monthly official exchange rates (local currency units per USD, period average), 2015 to Sept 2026, for 199 countries (188 after cleaning). Boundaries come from Natural Earth.

**Q: What does the exchange-rate value mean?**
A: How many units of the local currency equal 1 US dollar. A higher number means a weaker local currency.

**Q: What does pandas do in your project?**
A: It reads the Excel file, removes the junk row, parses dates, fills small gaps, maps country names to ISO3 codes, reshapes wide to long with `melt`, and computes the month-on-month, year-on-year and index columns.

**Q: Did you change the original Excel file?**
A: No. It is only read. Everything we create is written to new CSV/GPKG files.

**Q: Why reshape from wide to long?**
A: Models and maps need one row per country per month. The original has one column per country.

**Q: How did you handle missing values?**
A: Countries with more than 12 missing months since 2015 are dropped (11 countries). Smaller interior gaps are linearly interpolated, and a few edge months are filled by copying the nearest value.

**Q: Why derive percent change and an index?**
A: Raw rates aren't comparable across countries (about 90 for INR vs about 16,000 for IDR per USD). Percent changes put all countries on the same scale.

**Q: What is ARIMA?**
A: AutoRegressive Integrated Moving Average: it forecasts using past values (AR), differencing to remove trend (I) and past errors (MA). Written ARIMA(p, d, q).

**Q: What is SARIMA, and how is it different?**
A: ARIMA plus a seasonal component that repeats every 12 months. We use seasonal order (0,1,1,12).

**Q: Which one do you actually use?**
A: Both. For every country we fit ARIMA and SARIMA, compare them on a 12-month test, and use the better one for the forecast.

**Q: How do you pick p, d, q?**
A: d from the ADF stationarity test (0 if stationary, else 1). p and q by trying all combinations from 0 to 2 and choosing the lowest AIC.

**Q: What is the ADF test?**
A: Augmented Dickey-Fuller. It tests whether a series is stationary. A p-value below 0.05 means stationary, so d = 0.

**Q: What is AIC?**
A: A score that rewards good fit and penalises extra complexity. Lower is better.

**Q: Why use the logarithm?**
A: It stabilises large swings and makes changes proportional, so currencies of different sizes behave similarly. We convert back with `exp()`.

**Q: How do you check accuracy?**
A: We hide the last 12 months, train on the rest, forecast those 12 months and compare with reality using RMSE and MAPE.

**Q: What are RMSE and MAPE?**
A: RMSE is the typical error in the currency's own units. MAPE is the average percentage error. MAPE is comparable across countries and RMSE is not.

**Q: What is "naive" and why include it?**
A: Naive repeats the last observed value. It is the baseline: a model is only useful if it beats it. It is not a correlation method.

**Q: Why did the naive model beat ARIMA/SARIMA for many countries?**
A: Exchange rates behave much like a random walk, so the last value is already a strong forecast. That is a well-known result in economics. Our final map still uses ARIMA/SARIMA (as the brief requires), and the naive scores are reported as a benchmark.

**Q: What does the 95% interval mean?**
A: The range where, under the model's assumptions, the true value should fall about 95% of the time. It widens the further ahead we forecast.

**Q: Why 12 months for the forecast?**
A: It matches the 12-month test period and a full seasonal cycle, and longer exchange-rate forecasts become very unreliable.

**Q: Why only 20 countries?**
A: To keep it fast and readable for the demo: major economies across all regions. Setting `COUNTRIES = None` runs all 188.

**Q: Why is Argentina's error so high?**
A: A currency crisis happened inside the test window, and ARIMA/SARIMA assume past patterns continue. It is a good example of model limits.

**Q: What is a choropleth map?**
A: A map where regions are shaded by a data value. Ours shades by the 12-month change in the exchange rate.

**Q: What is a GeoPackage, and why use it?**
A: An open single-file spatial database format. It keeps geometry and attributes together and supports a real DateTime field for QGIS.

**Q: Why is the file so large compared with the CSV?**
A: Each country's polygon is repeated once per month (3,366 features for 20 countries x 153 months). We simplify the shapes to keep it manageable.

**Q: How does the Temporal Controller work?**
A: We tell QGIS that the `date` field gives each feature its time. QGIS then shows only features within the current time step, and playing the animation moves the step forward one month at a time.

**Q: Why is `yoy_pct_clip` used instead of `yoy_pct`?**
A: A few extreme values (hyperinflation currencies) would stretch the colour scale. Capping at -50 / +100 for colouring keeps the map readable. The true values remain in `yoy_pct`.

**Q: What does red vs green mean on your map?**
A: Red = currency weakened against the USD over the last 12 months. Green = strengthened.

**Q: What are the limitations?**
A: See section 10. The main ones: a single test window, model selection on the same test set, narrow model search, hidden convergence warnings, and exchange rates being close to a random walk.

**Q: How would you improve it?**
A: Rolling-origin cross-validation, residual diagnostics (Ljung-Box), an interval coverage check, other indicators (inflation, exports, imports), more countries, and models with explanatory variables (SARIMAX).

**Q: Why not use all five indicators in the brief?**
A: We built the full pipeline for one indicator (exchange rates). The same steps apply to the others once their data files are loaded.

**Q: Can you explain what one line of code does?**
A: Use section 5 and 6.2 as your guide: each step in the tables maps to a block in the scripts, and every script has its steps documented in the header comment.

---

## 13. Glossary

| Term | Plain-English meaning |
|---|---|
| **LCU** | Local Currency Unit (rupee, yen, peso...) |
| **USD** | US dollar |
| **GEM** | Global Economic Monitor, a World Bank dataset |
| **Period average** | The average over the month, not the end-of-month value |
| **ISO3** | International 3-letter country code (IND, JPN, USA) |
| **Wide / long format** | Wide = one column per country. Long = one row per country-month |
| **melt** | The pandas function that converts wide to long |
| **Interpolation** | Filling a gap by drawing a line between neighbouring known values |
| **DataFrame** | A pandas table |
| **Time series** | Values recorded over time in order |
| **Stationary** | A series with no drift in its average or spread |
| **Differencing** | Replacing values by their change from the previous value |
| **ADF test** | Statistical test for stationarity |
| **AR / MA / I** | AutoRegressive, Moving Average, Integrated (differencing) |
| **Seasonality** | A pattern that repeats at a fixed interval (every 12 months) |
| **AIC** | Model quality score. Lower is better |
| **Holdout / test set** | Data hidden from the model to test its forecasts |
| **RMSE** | Root Mean Squared Error (in the data's units) |
| **MAPE** | Mean Absolute Percentage Error (in %) |
| **Naive forecast** | "Next value = last value" baseline |
| **Confidence / prediction interval** | Range expected to contain the true value with a stated probability (95%) |
| **Vector data** | Maps made of points, lines and polygons |
| **Choropleth** | A map with regions shaded by a value |
| **GeoPandas** | A pandas extension that handles geographic data |
| **GeoPackage (.gpkg)** | A single-file spatial database format |
| **CRS / EPSG:4326** | Coordinate reference system. 4326 = ordinary longitude/latitude (WGS84) |
| **Natural Earth** | Free public-domain world map data |
| **Quantile classification** | Colour classes that each hold about the same number of features |
| **Temporal Controller** | The QGIS panel that animates data by time |
| **joblib** | Python library used to run country models in parallel |

---

## 14. Suggested demo flow (5 minutes)

1. **(30 s)** Say the pitch from section 1 and show the pipeline diagram from section 3.
2. **(30 s)** Open the original xlsx: "wide format, one column per country, 199 countries".
3. **(30 s)** Run `python 01_preprocess.py` and show the 3 output lines (188 countries, 141 months). Open `exchange_rate_long.csv` and point to `rate`, `yoy_pct`, `index_100`.
4. **(60 s)** Open `data/forecasts.csv` for India: real rows (`actual`) then 12 forecast rows with `lower`/`upper`. Open `model_metrics.csv`: explain `order`, naive vs ARIMA vs SARIMA MAPE, and why SARIMA won for India.
   *(Run script 2 **before** the demo; it takes a few minutes. Run it live only if the teacher asks.)*
5. **(30 s)** Run `python 03_build_qgis_layer.py` and explain the "one row per country per month" idea.
6. **(90 s)** In QGIS: show the graduated colours, then press play on the Temporal Controller and narrate: "red = currency weakening, green = strengthening; after Sept 2026 the colours come from our forecasts."
7. **(30 s)** Finish with limitations (section 10) and the improvements you would make.

**Splitting the talking:** one person covers data + pandas + QGIS (sections 4, 5, 7, 8) and the other covers ARIMA/SARIMA + results (sections 6, 9). But **read all of the Q&A together**, so either of you can answer any question.
