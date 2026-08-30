# HeatLens

Street photos + FortyGuard street ΔT → map the hottest streets → rank where extra canopy would cut ΔT most.

Demo cities: **Atlanta** and **Chicago**. Temperatures are never invented.

---

## What is actually built

| Piece | What it does | What it is not |
|---|---|---|
| Map (`web/`) | OpenFreeMap + coloured street markers from labelled ΔT | Live hourly weather map |
| Street panel | Name (Photon/Nominatim), ΔT, Urban Form bars, Action | 12-hour forecast bars |
| SegFormer-B0 (frozen) | Photo → canopy / asphalt / sky / building fractions | A trained heat vision net |
| OLS (`coefficients.json`) | `ΔT = a + b·canopy + c·asphalt + d·sky + e·building` | Per-city models; deep learning |
| `/forecast` | One **lagged** FortyGuard citywide mean (~7 days) | Synthetic 12-hour series |
| `/recommend` | `cooling ≈ −β_canopy × (0.40 − current canopy)` | Causal “trees will cool X°C” |
| `/validate` | Linear ΔT vs FortyGuard labelled ΔT | Proof the model generalises |

**Shipped numbers (pooled Atlanta + Chicago):** 2411 streets (1525 ATL + 886 CHI). Canopy coeff ≈ **−1.12**. Test R² is near zero / negative — map dots use **FortyGuard labels**, not the linear prediction.

**Formula we serve:** `T_street(t) = FortyGuard city snapshot(t) + ΔT_street`. City snapshot needs a per-state API key. ΔT on the map comes from the label file even if the key is missing.

---

## Run from scratch

### 0. You need

- Python 3.9+ (3.12 is fine; this repo’s venv may be 3.14)
- Node **22** (`web/.nvmrc`)
- FortyGuard keys: one account is **locked to one US state**. Atlanta = GA, Chicago = IL.
- Three artifacts (gitignored — not in the repo):
  - `data/labels.csv`
  - `data/segments.json`
  - `data/coefficients.json`

If you do not have those three files, build them (step 3) before the map will show dots.

### 1. Backend

```bash
git clone <this-repo>
cd heatlens-street-thermal
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` (do not commit it):

```
FORTYGUARD_API_KEY_ATLANTA=<georgia-account-key>
FORTYGUARD_API_KEY_CHICAGO=<illinois-account-key>
FORTYGUARD_API_KEY=<optional shared fallback>
FORTYGUARD_BASE_URL=https://api.fortyguard.com
MAPILLARY_ACCESS_TOKEN=<only needed to pull new photos>
HEATLENS_SEGMENTS_PATH=data/segments.json
HEATLENS_LABELS_PATH=data/labels.csv
HEATLENS_COEFFICIENTS_PATH=data/coefficients.json
HEATLENS_CACHE_PATH=data/cache/heatlens.sqlite
HEATLENS_ALLOWED_ORIGINS=http://localhost:3000
```

```bash
uvicorn api.main:app --reload --port 8000
```

Open http://localhost:8000/docs and http://localhost:8000/health  
`capabilities.fortyguard` should be `true` if a key is set.

### 2. Website

```bash
cd web
nvm use          # Node 22
npm install
npm run dev
```

http://localhost:3000 — city pill is **Atlanta, GA** and **Chicago, IL** only.

### Deploy the website (Vercel)

Config file: `web/vercel.json`. FastAPI does **not** run on Vercel — only the Next app. The API stays on Render/Railway/a VM.

1. Push the repo to GitHub.
2. [vercel.com/new](https://vercel.com/new) → Import the repo.
3. **Root Directory:** `web` (Edit → select `web`). Framework: Next.js.
4. Environment variable:

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | public URL of the running API, no trailing slash (e.g. `https://heatlens-api.onrender.com`) |

5. Deploy.

CLI from this repo:

```bash
cd web
npx vercel
```

On the API host, add the Vercel origin to `HEATLENS_ALLOWED_ORIGINS` (comma-separated), e.g. `http://localhost:3000,https://your-app.vercel.app`, then restart uvicorn.

### 3. Data (if `data/` is empty)

Photos and CSVs are gitignored (`delivery_*`, `data/labels.csv`, `data/segments.json`, `data/coefficients.json`).

**Already have the three files:** put them in `data/` and restart the API.

**Rebuild from teammate dumps + Colab (what we did):**

1. Unzip Atlanta + Chicago deliveries (labels CSV + `{image_id}.jpg`).
2. Upload to Drive `MyDrive/heatlens/`:
   - `labels_atlanta.csv` (Atlanta rows with fractions already filled), or last run’s `labels.csv`
   - `delivery_chicago_full.zip`
3. Colab: `notebooks/heatlens_pooled_colab.ipynb` → Runtime **T4 GPU** → Run all.  
   Frozen SegFormer fills Chicago fractions; OLS fits **one** pooled model.
4. Copy downloads into `data/`:

```bash
cp labels.csv data/labels.csv
cp coefficients.json data/coefficients.json
cp segments.json data/segments.json
```

**Local merge + fit** (after both CSVs have fractions; no GPU):

```bash
python -m heatlens.ml.pool \
  --labels data/labels.csv \
  --labels path/to/chicago_filled.csv \
  --fit-linear --write-segments
```

Do **not** fit Chicago-only and overwrite Atlanta coefficients. One `coefficients.json`.

### 4. Check

```bash
source .venv/bin/activate
pytest
curl -s http://localhost:8000/health
curl -s 'http://localhost:8000/segments?city=atlanta' | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])"
curl -s 'http://localhost:8000/segments?city=chicago' | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])"
```

Expect Atlanta **1525**, Chicago **886** if the pooled files are in place.

---

## API

| Endpoint | Needs | Returns |
|---|---|---|
| `GET /health` | — | capabilities (keys, files, model name) |
| `GET /cities` | — | study list (UI shows Atlanta + Chicago) |
| `GET /segments?city=atlanta` | `segments.json` | street points + fractions + ΔT |
| `GET /forecast?city=atlanta` | per-city FortyGuard key | one lagged city °C |
| `GET /absolute?city=atlanta` | key + segments | `city °C + ΔT` per street |
| `GET /recommend?city=atlanta` | coefficients + segments | ranked canopy actions + `canopy` coeff |
| `GET /validate?city=atlanta` | both | predicted vs labelled ΔT |
| `GET /street-name?lat=&lon=` | network | OSM road name (Photon, then Nominatim) |
| `POST /predict/features` | coefficients | ΔT from four fractions |
| `POST /predict` | ONNX vision model | **not wired** (`model: false`) |

---

## FortyGuard: one real request / response

FortyGuard: `POST /v1/heatmap` → poll `GET /v1/status/{activity_id}`.  
Header: `api-key` (not shown). One account = one US state.

Query date must be **lagged**. `today` returns `n_cells: 0`. We use ~**7 days back**, 14:00, 100 m tiles.

### Request (`POST https://api.fortyguard.com/v1/heatmap`)

Atlanta downtown bbox, 2026-08-23 14:00 (logged from this repo):

```json
{
  "polygon_aoi": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "properties": { "city": "atlanta" },
        "geometry": {
          "type": "Polygon",
          "coordinates": [[
            [-84.405286, 33.734627],
            [-84.370714, 33.734627],
            [-84.370714, 33.763373],
            [-84.405286, 33.763373],
            [-84.405286, 33.734627]
          ]]
        }
      }
    ]
  },
  "date_time": {
    "start_date": "2026-08-23",
    "start_time": "14:00",
    "filter_type": 1
  },
  "granularity": 100
}
```

### Submit response

```json
{
  "error": false,
  "data": {
    "activity_id": "1399da5e-da2b-4597-a672-6796daf018d9"
  }
}
```

### Completed job (truncated)

Real cached result from that Atlanta query: **960** tiles. City mean **34.37°C**. One tile shown; the rest omitted.

```json
{
  "map_data": {
    "type": "FeatureCollection",
    "features": [
      {
        "id": "0",
        "type": "Feature",
        "properties": {
          "tile_id": 0,
          "average_temperature": 34.3079,
          "min_temperature": 34.3079,
          "max_temperature": 34.3079
        },
        "geometry": {
          "type": "Polygon",
          "coordinates": [[
            [-84.404008, 33.735854],
            [-84.402938, 33.735831],
            [-84.402911, 33.736722],
            [-84.403981, 33.736745],
            [-84.404008, 33.735854]
          ]]
        }
      }
    ]
  },
  "stats_data": {
    "temperature_stats": {
      "minimum": 34.2827,
      "maximum": 34.482,
      "mean": 34.3655315625,
      "standard_deviation": 0.04974415558920302
    }
  }
}
```

`HeatLens /forecast` then returns:

```json
{
  "city": "atlanta",
  "source": "fortyguard",
  "points": [
    { "timestamp": "2026-08-23T14:00:00Z", "temperature_c": 34.3655315625 }
  ]
}
```

Street predicted temp (when the snapshot is up) = `34.37 + street ΔT`.  
Responses are cached in `data/cache/heatlens.sqlite` (no keys stored).

---

## Study cities (code vs demo)

| City | Role in code | Demo UI |
|---|---|---|
| Atlanta | train | yes |
| Chicago | train | yes |
| Phoenix, Houston | train (legacy) | hidden |
| Miami | holdout | hidden |
| Karachi, Lahore | transfer | hidden — **no FortyGuard**, do not claim °C |

---

## Rules we actually follow

- Never invent temperatures or hourly bars.
- Cache FortyGuard; ledger in `data/cache/`.
- Recommendations are **indicative** (0.4°C on a 0% canopy street is the linear signal, not a field trial).
- Winter / December photos vs summer FortyGuard labels — the OLS does not transfer street-by-street. Be honest in the demo.

---

## Future directions

- **Leaf-on imagery** (Jun–Aug). Most Mapillary frames here are Dec/Jan; that is why R² is poor and transfer-to-Lahore is unvalidated.
- **Per-city or hierarchical coeffs** once summer photos exist (do not overwrite the pooled file with a Chicago-only fit — Chicago has ~1 summer photo).
- **True hourly forecast** if FortyGuard exposes it; until then one lagged snapshot only.
- **More than trees:** cool pavement / shade as extra actions (today only canopy is ranked).
- **Holdout + transfer eval** (Miami, then Karachi/Lahore) with local labels — do not ship predicted °C there first.
- Wire `POST /predict` to an ONNX image model only after the linear baseline is honest on summer data.

---

## Repo map

```
api/                   FastAPI
web/                   Next.js map UI
heatlens/clients/      FortyGuard, Mapillary, Photon/Nominatim, SQLite cache
heatlens/ml/           SegFormer fractions, OLS, pooled merge
heatlens/ingest/       grid + dataset build
ingest/fortyguard.py   heatmap → tile ΔT (date lag)
notebooks/             Colab: Atlanta-only and pooled Atlanta+Chicago
data/                  runtime artifacts (gitignored)
tests/
```
