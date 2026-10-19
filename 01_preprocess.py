import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import pycountry
from pathlib import Path

XLSX = "Official_exchange_rate__LCU_per_USD__period_average.xlsx"
START = "2015-01-01"
MAX_MISSING = 12          
INTERP_METHOD = "linear"  
Z_THRESHOLD = 3.0       
IQR_FACTOR = 1.5      
VERBOSE = True           
OUT = Path("data"); OUT.mkdir(exist_ok=True)
(OUT / "analysis").mkdir(exist_ok=True)

def log(*a, **k):
    if VERBOSE:
        print(*a, **k)

def section(title):
    log(f"\n=== {title} ===")

NAME_FIX = {
    "Bahamas, The": "BHS", "Congo, Dem. Rep.": "COD", "Congo, Rep.": "COG", "Cote d'Ivoire": "CIV",
    "Egypt, Arab Rep.": "EGY", "Gambia, The": "GMB", "Hong Kong SAR, China": "HKG",
    "Iran, Islamic Rep.": "IRN", "Korea, Rep.": "KOR", "Kyrgyz Republic": "KGZ", "Lao, PDR": "LAO",
    "Macao SAR, China": "MAC", "Micronesia, Fed. Sts.": "FSM", "Moldova, Rep.": "MDA",
    "Netherlands Antilles": "ANT", "Russian Federation": "RUS", "Syrian Arab Republic": "SYR",
    "Taiwan, China": "TWN", "Tanzania, United Rep.": "TZA", "Venezuela, RB": "VEN",
    "Viet Nam": "VNM", "Yemen, Rep.": "YEM", "Virgin Islands, U.S.": "VIR", "West Bank and Gaza": "PSE",
    "St. Kitts and Nevis": "KNA", "St. Lucia": "LCA", "St. Vincent and the Grenadines": "VCT",
    "Cabo Verde": "CPV", "Czech Republic": "CZE", "Kosovo": "XKX", "Turkey": "TUR",
    "Eswatini": "SWZ", "Brunei Darussalam": "BRN", "Slovakia": "SVK",
}

def to_iso3(name):
    if name in NAME_FIX:
        return NAME_FIX[name]
    try:
        return pycountry.countries.lookup(name).alpha_3
    except LookupError:
        return None

raw = pd.read_excel(XLSX, sheet_name="monthly", header=0)
raw = raw.rename(columns={raw.columns[0]: "period"})
raw = raw[raw["period"].astype(str).str.match(r"^\d{4}M\d{2}$")].copy()
raw["date"] = pd.to_datetime(raw["period"].str.replace("M", "-") + "-01")
raw = raw.drop(columns="period").set_index("date")
raw = raw.apply(pd.to_numeric, errors="coerce")
raw = raw.loc[START:]

section("1. Raw data inspection")
log("Shape (months x countries):", raw.shape)
log("Date range:", raw.index.min().date(), "to", raw.index.max().date())
log("Datatypes:", {str(k): int(v) for k, v in raw.dtypes.value_counts().items()})
log("First 3 rows, first 4 countries:\n", raw.iloc[:3, :4].round(2).to_string())
log("Last 3 rows, first 4 countries:\n", raw.iloc[-3:, :4].round(2).to_string())

def find_spikes(s, factor=5.0):
    """One-month data-entry spikes: the value is >5x (or <1/5) of its neighbours AND the two neighbours
    are close to each other, i.e. the series jumps up/down for a single month and comes straight back."""
    prev, nxt = s.shift(1), s.shift(-1)
    neighbours_close = (prev / nxt).between(1 / 1.5, 1.5)
    ratio = s / ((prev + nxt) / 2)
    return neighbours_close & ((ratio > factor) | (ratio < 1 / factor))

section("2. Missing values and data-entry spikes BEFORE cleaning")
spikes = pd.DataFrame({c: find_spikes(raw[c]) for c in raw.columns})
spike_count = spikes.sum()
for c in spike_count[spike_count > 0].index:
    for d in spikes.index[spikes[c]]:
        log(f"  spike corrected: {c} {d:%Y-%m} had {raw.loc[d, c]:.2f} (neighbours about {raw[c].shift(1)[d]:.2f})")
raw = raw.mask(spikes)
miss = raw.isna().sum()
log("Missing cells:", int(miss.sum()), "| countries with any gap:", int((miss > 0).sum()),
    "| countries with > MAX_MISSING:", int((miss > MAX_MISSING).sum()))

def backtest_fill(df, n_hide=6, seed=42):
    rng = np.random.default_rng(seed)
    errors = {"mean": [], "linear": [], "polynomial": []}
    for c in df.columns:
        s = df[c]
        if s.isna().any() or s.nunique() < 3:
            continue
        pos = rng.choice(np.arange(1, len(s) - 1), size=n_hide, replace=False)
        masked = s.copy()
        masked.iloc[pos] = np.nan
        truth = s.iloc[pos].to_numpy()
        fills = {"mean": masked.fillna(masked.mean()),
                "linear": masked.interpolate(method="linear"),
                "polynomial": masked.interpolate(method="polynomial", order=2)}
        for name, filled in fills.items():
            errors[name].append(np.mean(np.abs((truth - filled.iloc[pos].to_numpy()) / truth)) * 100)
    return {k: float(np.median(v)) for k, v in errors.items() if v}

section("3. Gap-filling back-test: median % error when 6 known months are hidden")
try:
    bt = backtest_fill(raw)
    for name, err in bt.items():
        log(f"  {name:<11} {err:6.3f} %")
    log(f"  -> best in back-test: {min(bt, key=bt.get)} | used for the real gaps: {INTERP_METHOD} "
        "(linear and polynomial are almost identical, mean-filling is clearly worse)")
    pd.Series(bt, name="median_pct_error").to_csv(OUT / "analysis" / "gap_fill_backtest.csv")
except Exception as e:
    log("  back-test skipped:", e)

report = []
clean = {}
interp_kw = {"method": INTERP_METHOD, "limit_area": "inside"}
if INTERP_METHOD == "polynomial":
    interp_kw["order"] = 2
for country in raw.columns:
    s = raw[country]
    n_miss = int(s.isna().sum())
    if s.isna().all() or n_miss > MAX_MISSING:
        report.append((country, n_miss, "dropped: too many missing months"))
        continue
    s = s.interpolate(**interp_kw)  
    s = s.ffill().bfill()             
    clean[country] = s
    note = f" (incl. {int(spike_count[country])} data-entry spike)" if spike_count[country] else ""
    report.append((country, n_miss, "kept" if n_miss == 0 else f"kept: {n_miss} month(s) filled{note}"))
wide = pd.DataFrame(clean)

section("4. After cleaning")
log("Missing cells AFTER:", int(wide.isna().sum().sum()), "| countries kept:", wide.shape[1],
    "| dropped:", sum(1 for r in report if r[2].startswith("dropped")))


iso = {c: to_iso3(c) for c in wide.columns}
unmapped = [c for c, i in iso.items() if i is None]
if unmapped:
    print("WARNING - no ISO3 for:", unmapped, "-> add them to NAME_FIX")
wide = wide[[c for c in wide.columns if iso[c]]]

long = (wide.rename_axis("date").reset_index()
            .melt(id_vars="date", var_name="country", value_name="rate")
            .sort_values(["country", "date"]))

dups = int(long.duplicated(["country", "date"]).sum())      
long = long.drop_duplicates(["country", "date"])
section("5. Long table")
log("Duplicate country-month rows removed:", dups)

g = long.groupby("country")["rate"]
long["pct_change_mom"] = g.pct_change() * 100
long["yoy_pct"] = g.pct_change(12) * 100
long["index_100"] = long["rate"] / g.transform("first") * 100
long["iso3"] = long["country"].map(iso)
long = long[["country", "iso3", "date", "rate", "pct_change_mom", "yoy_pct", "index_100"]]


gm = long.groupby("country")["pct_change_mom"]
z = (long["pct_change_mom"] - gm.transform("mean")) / gm.transform("std")
q1, q3 = gm.transform(lambda s: s.quantile(0.25)), gm.transform(lambda s: s.quantile(0.75))
iqr = q3 - q1
long["outlier_z"] = (z.abs() > Z_THRESHOLD).astype(int)
long["outlier_iqr"] = (((long["pct_change_mom"] < q1 - IQR_FACTOR * iqr) |
                        (long["pct_change_mom"] > q3 + IQR_FACTOR * iqr)) & (iqr > 0)).astype(int)

out_rep = (long.assign(abs_move=long["pct_change_mom"].abs())
               .groupby(["country", "iso3"])
               .agg(outliers_z=("outlier_z", "sum"), outliers_iqr=("outlier_iqr", "sum"),
                    largest_monthly_move_pct=("pct_change_mom", lambda s: s.loc[s.abs().idxmax()] if s.notna().any() else np.nan))
               .reset_index())
out_rep.to_csv(OUT / "outlier_report.csv", index=False)

section("6. Outliers in monthly % change (flagged, not removed)")
log(f"Z-score (|Z| > {Z_THRESHOLD}): {int(long['outlier_z'].sum())} country-months in "
    f"{int((out_rep['outliers_z'] > 0).sum())} countries")
log(f"IQR ({IQR_FACTOR} x IQR rule): {int(long['outlier_iqr'].sum())} country-months in "
    f"{int((out_rep['outliers_iqr'] > 0).sum())} countries")
big = long.reindex(long["pct_change_mom"].abs().sort_values(ascending=False).index).head(5)
log("Five biggest one-month moves (genuine rate changes/devaluations; typos were removed in section 2):")
for _, r in big.iterrows():
    log(f"  {r['country']:<22} {r['date']:%Y-%m}  {r['pct_change_mom']:+7.1f} %")


section("7. Final table and insights")
if VERBOSE:
    long.info()
    print(long[["rate", "pct_change_mom", "yoy_pct", "index_100"]].describe().round(2).to_string())
last = long[long["date"] == long["date"].max()]
top = last.loc[last["index_100"].idxmax()]
log("Insights (calculated from the data):")
log(f"  1. {top['country']} had the biggest depreciation vs USD since Jan 2015 (index {top['index_100']:.0f}).")
log(f"  2. {int(long['outlier_z'].sum())} Z-score outlier months, mostly genuine devaluations; "
    f"{int(spike_count.sum())} data-entry spike(s) were corrected instead of kept.")

long.to_csv(OUT / "exchange_rate_long.csv", index=False)
pd.DataFrame(report, columns=["country", "missing_months", "decision"]).to_csv(OUT / "preprocess_report.csv", index=False)

print(f"\nCountries kept: {long['country'].nunique()}  |  months: {long['date'].nunique()}  |  rows: {len(long)}")
print(f"Range: {long['date'].min():%Y-%m} to {long['date'].max():%Y-%m}")
print("Dropped:", [r[0] for r in report if r[2].startswith("dropped")])
