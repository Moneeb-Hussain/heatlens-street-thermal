"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getCities, getValidate } from "@/lib/api";
import { sortCities } from "@/lib/cities";
import type { ValidatePair } from "@/lib/types";

function mae(pairs: ValidatePair[]): number | null {
  const scored = pairs.filter((row) => row.predicted_delta_t != null);
  if (!scored.length) return null;
  const total = scored.reduce(
    (sum, row) => sum + Math.abs((row.predicted_delta_t as number) - row.reference_delta_t),
    0
  );
  return total / scored.length;
}

export default function ValidatePage() {
  const [cities, setCities] = useState<City[]>([]);
  const [cityId, setCityId] = useState("atlanta");
  const [pairs, setPairs] = useState<ValidatePair[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fromQuery = (params.get("city") || "").toLowerCase();
    if (fromQuery) setCityId(fromQuery);
    getCities()
      .then((list) => setCities(list))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    let cancelled = false;
    getValidate(cityId)
      .then((body) => {
        if (!cancelled) {
          setPairs(body.pairs);
          setError(null);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setPairs([]);
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [cityId]);

  const errorMae = useMemo(() => mae(pairs), [pairs]);
  const predictedN = pairs.filter((row) => row.predicted_delta_t != null).length;

  return (
    <div className="app">
      <header className="topbar">
        <span className="logo">
          Heat<span className="logo-lens">Lens</span>
        </span>
        <label className="city-pill">
          <select value={cityId} onChange={(event) => setCityId(event.target.value)}>
            {sortCities(cities).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <div className="top-links">
          <Link href="/">Map</Link>
          <div className="live-pill">
            {pairs.length} streets · MAE {errorMae == null ? "—" : `${errorMae.toFixed(2)}°`}
          </div>
        </div>
      </header>
      {error && <p className="error">{error}</p>}
      <div className="validate-shell">
      <aside className="feat-section">
        <h2>Predictions vs FortyGuard</h2>
        <p className="muted">
          Linear ΔT from street fractions vs labelled street ΔT. No invented temperatures.
        </p>
        <p className="muted">
          {predictedN
            ? `${predictedN} streets have a linear prediction.`
            : "coefficients.json missing — FortyGuard column only."}
        </p>
      </aside>
      <main className="validate-table-wrap">
        <div className="validate-cols">
          <h2>Street</h2>
          <h2>Our ΔT</h2>
          <h2>FortyGuard ΔT</h2>
        </div>
        {!pairs.length && <p className="muted">No segments yet for this city.</p>}
        <div className="validate-table">
          {pairs.slice(0, 80).map((row) => (
            <div className="validate-row" key={row.image_id}>
              <span className="muted">{row.image_id}</span>
              <b>{row.predicted_delta_t == null ? "—" : `${row.predicted_delta_t.toFixed(2)} °C`}</b>
              <b>{row.reference_delta_t.toFixed(2)} °C</b>
            </div>
          ))}
        </div>
        {pairs.length > 80 && <p className="muted">Showing first 80 of {pairs.length}.</p>}
      </main>
      </div>
    </div>
  );
}
