"use client";

import type { Capabilities, City, RecommendItem, Segment } from "@/lib/types";

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
};

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
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
}: Props) {
  const city = cities.find((item) => item.id === cityId);
  const missing = [];
  if (capabilities && !capabilities.segments) missing.push("no segments.json yet");
  if (capabilities && !capabilities.fortyguard) missing.push("FortyGuard key not set");
  if (capabilities && !capabilities.model) missing.push("vision model not trained");

  return (
    <aside className="panel">
      <div className="brand">
        <p>HeatLens</p>
        <h1>Street thermal map</h1>
      </div>

      <label>
        <span className="empty">City</span>
        <select value={cityId} onChange={(event) => onCity(event.target.value)}>
          {cities.map((item) => (
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

      {missing.length > 0 && (
        <div className="banner warn">
          Live capabilities: {missing.join(" · ")}. The map stays empty until ingest writes
          data/segments.json. No synthetic heat is shown.
        </div>
      )}

      {loadError && <div className="error">{loadError}</div>}

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
            : "Run ingest after keys are set. This skeleton will not invent street temperatures."}
        </p>
      )}

      <section>
        <h2>Canopy shortlist</h2>
        {recommendError && <p className="empty">{recommendError}</p>}
        {!recommendError && recommendations.length === 0 && (
          <p className="empty">Needs fitted data/coefficients.json from evaluation.</p>
        )}
        {recommendations.slice(0, 8).map((item) => (
          <div className="frac" key={item.image_id}>
            <span>{item.image_id}</span>
            <span>{item.estimated_cooling_c.toFixed(2)} °C cooling*</span>
          </div>
        ))}
        {recommendations.length > 0 && (
          <p className="empty">*Indicative. Not a causal guarantee.</p>
        )}
      </section>
    </aside>
  );
}
