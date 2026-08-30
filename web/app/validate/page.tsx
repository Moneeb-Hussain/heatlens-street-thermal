"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getCities, getValidate } from "@/lib/api";
import type { City, ValidatePair } from "@/lib/types";

const CITY_ORDER = ["atlanta", "chicago", "phoenix", "houston", "miami", "karachi", "lahore"];

function sortCities(cities: City[]): City[] {
  return [...cities].sort((a, b) => {
    const ia = CITY_ORDER.indexOf(a.id);
    const ib = CITY_ORDER.indexOf(b.id);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

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
    <div className="shell validate-shell">
      <aside className="panel">
        <div className="brand">
          <p>HeatLens</p>
          <h1>Check predictions</h1>
          <nav className="nav">
            <Link href="/">Map</Link>
            <Link href={`/validate?city=${encodeURIComponent(cityId)}`}>Check</Link>
          </nav>
        </div>
        <label>
          <span className="empty">City</span>
          <select value={cityId} onChange={(event) => setCityId(event.target.value)}>
            {sortCities(cities).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.role}
              </option>
            ))}
          </select>
        </label>
        <p className="empty">
          Linear ΔT from street fractions vs FortyGuard street ΔT. No invented temperatures.
        </p>
        {error && <div className="error">{error}</div>}
        <div className="stat-row">
          <div className="stat">
            <b>{pairs.length}</b>
            <span>streets</span>
          </div>
          <div className="stat">
            <b>{errorMae == null ? "—" : `${errorMae.toFixed(2)}°`}</b>
            <span>MAE</span>
          </div>
        </div>
        <p className="empty">
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
        {!pairs.length && <p className="empty">No segments yet for this city.</p>}
        <div className="validate-table">
          {pairs.slice(0, 80).map((row) => (
            <div className="validate-row" key={row.image_id}>
              <span className="empty">{row.image_id}</span>
              <b>{row.predicted_delta_t == null ? "—" : `${row.predicted_delta_t.toFixed(2)} °C`}</b>
              <b>{row.reference_delta_t.toFixed(2)} °C</b>
            </div>
          ))}
        </div>
        {pairs.length > 80 && <p className="empty">Showing first 80 of {pairs.length}.</p>}
      </main>
    </div>
  );
}
