# HeatLens

Street photos + FortyGuard temperature → map of which streets are hottest → rank where to plant trees first.

**3-day hackathon. Two people:**
- **AI person** — trains the vision model (`heatlens/ml/`, `models/`)
- **You** — get the data, run the API, finish the website (`ingest/`, `api/`, `web/`)

---

## Setup (do this once)

### 1. Python backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Add your keys to `.env`:
```
FORTYGUARD_API_KEY=...
MAPILLARY_ACCESS_TOKEN=...
```

Start the API:
```bash
uvicorn api.main:app --reload --port 8000
```
→ http://localhost:8000/docs

### 2. Website

```bash
cd web
nvm use          # needs Node 22 — see web/.nvmrc
npm install
npm run dev
```
→ http://localhost:3000

### 3. Quick check

```bash
pytest                                    # should pass
python -m heatlens.ingest.build --json    # grid counts per city
```

---

## What's already built (skeleton)

| Part | Status | What it does |
|---|---|---|
| **API** (`api/`) | ✅ Running | `/health`, `/cities`, `/segments`, `/forecast`, `/recommend`, etc. |
| **Website** (`web/`) | ✅ Running | Map + city picker + side panel. Empty until data exists. |
| **FortyGuard client** | ✅ Ready | Submit heatmap → poll → get temperature. Caches responses. |
| **Mapillary client** | ✅ Ready | Find best photo within 50m of a point. |
| **Grid sampler** | ✅ Ready | 50m points across each city + 1km block IDs. |
| **Photo filters** | ✅ Ready | Rejects panos, fisheye, night shots, low quality. |
| **ML metrics / splits** | ✅ Ready | MAE, R², spatial-block leak checks. |
| **Agent tools** | ✅ Ready | `list_cities`, `list_segments`, `rank_interventions`. |
| **Tests** | ✅ 23 passing | Domain, API, clients. |

**Important:** nothing shows fake heat. Map stays empty until you add real data files.

---

## What YOU still need to build

| Priority | Task | File(s) | Why |
|---|---|---|---|
| 🔴 Day 1 | Put API keys in `.env` | `.env` | Nothing works without keys |
| 🔴 Day 1 | Check photo coverage per city | run `ingest.build --json` | Swap city if no photos |
| 🔴 Day 1–2 | Download street photos | `data/raw/` | Training needs images |
| 🔴 Day 1–2 | Build labelled dataset | `data/labels.csv` | AI person trains on this |
| 🔴 Day 2 | Map data file | `data/segments.json` | Map shows dots |
| 🟡 Day 2–3 | Wire live forecast + time slider | `api/routes.py`, `web/` | FortyGuard 12h forecast |
| 🟡 Day 3 | Validation view | `web/` | Our predictions vs FortyGuard heatmap |
| 🟡 Day 3 | Deploy + demo video | Vercel + Render | Submission |

### Files you own — don't touch AI person's code

```
ingest/imagery.py      ← finish: bulk photo download from Mapillary
ingest/fortyguard.py   ← finish: pull delta_t labels from FortyGuard heatmaps
ingest/build.py        ← finish: grid → photo → label → labels.csv (one command)
api/                   ← keep thin, add export CSV if time
web/                   ← map polish, time slider, validation page
data/                  ← all runtime files live here (not committed to git)
agent/tools.py         ← MCP agent wrapper
```

### Files AI person owns — don't touch these

```
heatlens/ml/           ← training, evaluation, segmentation
models/train.py        ← fine-tune vision model
models/segment.py      ← SegFormer feature extraction
models/evaluate.py     ← score predictions
```

---

## Your 3-day plan

| Day | Do | Deliver to AI person |
|---|---|---|
| **1** | Keys in `.env`. Run grid counts. Start downloading photos. Try Mapillary + FortyGuard on Phoenix first. | Message: "X photos in Phoenix, keys work" |
| **2** | Finish `labels.csv` + `data/raw/`. Write `segments.json`. Map shows real dots. | `labels.csv` + images (this unblocks training) |
| **3** | Forecast slider, validation view, deploy, demo video | Working demo URL |

---

## Data files explained

### `data/labels.csv` — training dataset (AI person needs this)

| Column | Example | Source |
|---|---|---|
| `image_id` | `mapillary_abc123` | Mapillary |
| `lat`, `lon` | `33.45, -112.07` | Photo GPS |
| `city` | `phoenix` | You assign |
| `block_id` | `b_14_22` | Auto from grid |
| `delta_t` | `-3.1` or `+5.2` | FortyGuard (°C vs city mean) |
| `canopy_frac` | `0.42` | SegFormer (AI person fills later) |
| `asphalt_frac` | `0.31` | SegFormer |
| `sky_frac` | `0.18` | SegFormer |
| `building_frac` | `0.09` | SegFormer |
| `split` | `train` / `test` / `holdout_city` | 1km blocks, Miami = holdout |

### `data/segments.json` — what the map reads

Same info as labels but in JSON. One entry per street point with `lat`, `lon`, `delta_t`, feature fractions.

### `data/coefficients.json` — ranking (AI person gives you this)

Fitted numbers for "how much cooling per unit of extra tree cover." Powers `/recommend`.

---

## API endpoints

| Endpoint | Needs | Returns |
|---|---|---|
| `GET /health` | nothing | what's configured |
| `GET /cities` | nothing | Phoenix, Atlanta, Houston, Miami, Karachi, Lahore |
| `GET /segments?city=phoenix` | `segments.json` | street points (empty list if no file) |
| `GET /forecast?city=phoenix` | FortyGuard key | city temperature snapshot |
| `GET /absolute?city=phoenix` | FortyGuard key + segments | street temp = forecast + delta_t |
| `GET /recommend?city=phoenix` | coefficients.json + segments | ranked tree-planting list |
| `POST /predict` | trained model | delta_t from uploaded photo |

Full docs: http://localhost:8000/docs

---

## Study cities

| City | Role | Notes |
|---|---|---|
| Phoenix | train | Low trees, very hot |
| Atlanta | train | High trees — model sees both extremes |
| Houston | train | Mixed |
| Miami | holdout | Never used in training — tests generalisation |
| Karachi / Lahore | transfer only | No FortyGuard — mark **unvalidated** on map |

---

## Rules

- **Never invent temperatures.** Empty map > fake data.
- **Cache every FortyGuard call.** Credit ledger in `data/cache/`.
- **Karachi/Lahore** labelled unvalidated in the UI.
- **Recommendations** labelled indicative (not guaranteed cooling).
- **Stuck?** Message the AI person. Don't guess.

---

## Handoffs between you two

| When | From → To | File |
|---|---|---|
| End Day 2 | You → AI | `labels.csv` + `data/raw/` |
| End Day 3 | AI → You | `data/segments.json` (with model predictions) |
| Day 3 | AI → You | `data/coefficients.json` (for ranked list) |
| Day 3 | You → AI | FortyGuard heatmap screenshot (for validation figure) |
