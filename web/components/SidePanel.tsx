"use client";

import Link from "next/link";
import type { Capabilities, City, RecommendItem, Segment } from "@/lib/types";

export const FORECAST_HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18];

const CITY_ORDER = [
  "atlanta",
  "chicago",
  "phoenix",
  "houston",
  "miami",
  "karachi",
  "lahore",
];

type Props = {
  cities: City[];
  cityId: string;
  onCity: (id: string) => void;
  capabilities: Capabilities | null;
  segments: Segment[];
  selected: Segment | null;
  recommendations: RecommendItem[];
  recommendError: string | null;
  loadError: string | null;
  forecastHour: number;
  onForecastHour: (hour: number) => void;
  cityTemperatureC: number | null;
  forecastError: string | null;
  onSelect: (id: string) => void;
};

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function sortCities(cities: City[]): City[] {
  return [...cities].sort((a, b) => {
    const ia = CITY_ORDER.indexOf(a.id);
    const ib = CITY_ORDER.indexOf(b.id);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

function capabilityNotes(
  capabilities: Capabilities | null,
  segmentCount: number
): string[] {
  if (!capabilities) return [];
  const notes: string[] = [];
  if (!capabilities.segments && segmentCount === 0) {
    notes.push("No segments.json yet — the map is empty until ingest writes street dots.");
  }
  if (!capabilities.coefficients) {
    notes.push("No coefficients.json — canopy ranking is unavailable.");
  }
  if (!capabilities.fortyguard) {
    notes.push("Live city forecast needs a FortyGuard key. Map still shows ΔT vs city mean.");
  }
  return notes;
}

export default function SidePanel({
  cities,
  cityId,
  onCity,
  capabilities,
  segments,
  selected,
  recommendations,
  recommendError,
  loadError,
  forecastHour,
  onForecastHour,
  cityTemperatureC,
  forecastError,
  onSelect,
}: Props) {
  const city = cities.find((item) => item.id === cityId);
  const notes = capabilityNotes(capabilities, segments.length);
  const absoluteC =
    selected && cityTemperatureC != null ? cityTemperatureC + selected.delta_t : null;

  return (
    <aside className="panel">
      <div className="brand">
        <p>HeatLens</p>
        <h1>Street thermal map</h1>
        <nav className="nav">
          <Link href="/">Map</Link>
          <Link href={`/validate?city=${encodeURIComponent(cityId)}`}>Check</Link>
        </nav>
      </div>

      <label>
        <span className="empty">City</span>
        <select value={cityId} onChange={(event) => onCity(event.target.value)}>
          {sortCities(cities).map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} · {item.role}
            </option>
          ))}
        </select>
      </label>

      {city && (
        <div className="meta">
          <span className="pill">{city.role}</span>
          <span className="pill">{city.coverage_validated ? "US labelled" : "unvalidated transfer"}</span>
        </div>
      )}

      {notes.map((note) => (
        <div className="banner warn" key={note}>
          {note}
        </div>
      ))}

      {loadError && <div className="error">{loadError}</div>}

      <label>
        <span className="empty">City forecast hour (UTC, 7-day lag)</span>
        <input
          type="range"
          min={FORECAST_HOURS[0]}
          max={FORECAST_HOURS[FORECAST_HOURS.length - 1]}
          step={1}
          value={forecastHour}
          onChange={(event) => onForecastHour(Number(event.target.value))}
          disabled={!capabilities?.fortyguard}
        />
        <div className="frac">
          <span>{forecastHour}:00</span>
          <b>
            {cityTemperatureC != null
              ? `${cityTemperatureC.toFixed(1)} °C city`
              : "—"}
          </b>
        </div>
      </label>
      {forecastError && <p className="empty">{forecastError}</p>}
      {!forecastError && capabilities?.fortyguard && cityTemperatureC != null && (
        <p className="empty">Street °C = city forecast + ΔT. Dots stay ΔT so we do not invent heat.</p>
      )}

      <div className="stat-row">
        <div className="stat">
          <b>{segments.length}</b>
          <span>segments</span>
        </div>
        <div className="stat">
          <b>
            {segments.length
              ? `${Math.max(...segments.map((s) => s.delta_t)).toFixed(1)}°`
              : "—"}
          </b>
          <span>hottest ΔT</span>
        </div>
      </div>

      {selected ? (
        <section>
          <h2>Selected street</h2>
          <p className="empty">{selected.image_id}</p>
          <div className="frac">
            <span>ΔT vs city mean</span>
            <b>{selected.delta_t.toFixed(2)} °C</b>
          </div>
          {absoluteC != null && (
            <div className="frac">
              <span>Street at this hour</span>
              <b>{absoluteC.toFixed(1)} °C</b>
            </div>
          )}
          <div className="frac">
            <span>Canopy</span>
            <span>{pct(selected.features.canopy_frac)}</span>
          </div>
          <div className="frac">
            <span>Asphalt</span>
            <span>{pct(selected.features.asphalt_frac)}</span>
          </div>
          <div className="frac">
            <span>Sky</span>
            <span>{pct(selected.features.sky_frac)}</span>
          </div>
          <div className="frac">
            <span>Building</span>
            <span>{pct(selected.features.building_frac)}</span>
          </div>
          <p className="empty">
            Source {selected.source}
            {selected.validated ? " · FortyGuard-validated" : " · unvalidated"}
          </p>
        </section>
      ) : (
        <p className="empty">
          {segments.length
            ? "Click a street marker to inspect ΔT and urban form."
            : "No segments yet for this city."}
        </p>
      )}

      <section>
        <h2>Canopy shortlist</h2>
        {recommendError && <p className="empty">{recommendError}</p>}
        {!recommendError && recommendations.length === 0 && (
          <p className="empty">
            {segments.length
              ? "Needs fitted data/coefficients.json from evaluation."
              : "No segments yet for this city."}
          </p>
        )}
        {recommendations.slice(0, 8).map((item) => (
          <button
            className={`frac rec${item.image_id === selected?.image_id ? " rec-on" : ""}`}
            key={item.image_id}
            type="button"
            onClick={() => onSelect(item.image_id)}
          >
            <span>{item.image_id}</span>
            <span>{item.estimated_cooling_c.toFixed(2)} °C cooling*</span>
          </button>
        ))}
        {recommendations.length > 0 && (
          <p className="empty">*Indicative. Not a causal guarantee.</p>
        )}
      </section>
    </aside>
  );
}
