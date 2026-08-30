"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { getCities, getForecast, getHealth, getRecommendations, getSegments, getStreetName } from "@/lib/api";
import { sortCities } from "@/lib/cities";
import type { Capabilities, City, RecommendItem, Segment } from "@/lib/types";
import StreetCard from "@/components/StreetCard";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

function lagTimestamp(hour: number): string {
  const day = new Date();
  day.setUTCDate(day.getUTCDate() - 7);
  day.setUTCHours(hour, 0, 0, 0);
  return day.toISOString();
}

const CITY_SUFFIX: Record<string, string> = {
  atlanta: "Atlanta, GA",
  chicago: "Chicago, IL",
  phoenix: "Phoenix, AZ",
  houston: "Houston, TX",
  miami: "Miami, FL",
  karachi: "Karachi",
  lahore: "Lahore",
};

export default function HomePage() {
  const [cities, setCities] = useState<City[]>([]);
  const [cityId, setCityId] = useState("atlanta");
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendItem[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [cityTemperatureC, setCityTemperatureC] = useState<number | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [streetName, setStreetName] = useState<string | null>(null);
  const [streetNameLoading, setStreetNameLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getHealth(), getCities()])
      .then(([health, list]) => {
        if (cancelled) return;
        setCapabilities(health.capabilities);
        setCities(list);
        if (list.length && !list.some((c) => c.id === cityId)) {
          setCityId((list.find((c) => c.id === "atlanta") ?? list[0]).id);
        }
      })
      .catch((error: Error) => {
        if (!cancelled) setLoadError(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setSelectedId(null);
    setStreetName(null);
    getSegments(cityId)
      .then((rows) => {
        if (!cancelled) setSegments(rows);
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setSegments([]);
          setLoadError(error.message);
        }
      });
    getRecommendations(cityId)
      .then((rows) => {
        if (!cancelled) setRecommendations(rows);
      })
      .catch(() => {
        if (!cancelled) setRecommendations([]);
      });
    return () => {
      cancelled = true;
    };
  }, [cityId]);

  useEffect(() => {
    if (!capabilities?.fortyguard) {
      setCityTemperatureC(null);
      setForecastLoading(false);
      return;
    }
    let cancelled = false;
    setForecastLoading(true);
    const handle = window.setTimeout(() => {
      getForecast(cityId, lagTimestamp(14))
        .then((body) => {
          if (!cancelled) setCityTemperatureC(body.points[0]?.temperature_c ?? null);
        })
        .catch(() => {
          if (!cancelled) setCityTemperatureC(null);
        })
        .finally(() => {
          if (!cancelled) setForecastLoading(false);
        });
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [cityId, capabilities]);

  const selected = useMemo(
    () => segments.find((row) => row.image_id === selectedId) ?? null,
    [segments, selectedId]
  );

  useEffect(() => {
    if (!selected) {
      setStreetName(null);
      setStreetNameLoading(false);
      return;
    }
    let cancelled = false;
    setStreetNameLoading(true);
    getStreetName(selected.lat, selected.lon)
      .then((name) => {
        if (!cancelled) setStreetName(name);
      })
      .catch(() => {
        if (!cancelled) setStreetName(null);
      })
      .finally(() => {
        if (!cancelled) setStreetNameLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const city = cities.find((row) => row.id === cityId) ?? null;
  const onSelect = useCallback((id: string) => setSelectedId(id), []);
  const selectedRec = recommendations.find((row) => row.image_id === selectedId) ?? null;
  const cityLabel = CITY_SUFFIX[cityId] ?? city?.name ?? cityId;

  return (
    <div className="app">
      <header className="topbar">
        <span className="logo">
          Heat<span className="logo-lens">Lens</span>
        </span>
        <label className="city-pill">
          <span className="city-dot" />
          <select value={cityId} onChange={(event) => setCityId(event.target.value)} aria-label="City">
            {sortCities(cities).map((item) => (
              <option key={item.id} value={item.id}>
                {CITY_SUFFIX[item.id] ?? item.name}
              </option>
            ))}
          </select>
        </label>
        <div className="top-links">
          <Link href={`/validate?city=${encodeURIComponent(cityId)}`}>Check</Link>
          <div className="live-pill">
            <div className="live-dot" />
            <span>
              {cityTemperatureC != null ? `${cityTemperatureC.toFixed(1)}°C LIVE` : "ΔT LIVE"}
            </span>
          </div>
        </div>
      </header>
      {loadError && <p className="error">{loadError}</p>}
      <div className="main">
        <div className="map-wrap">
          <MapView city={city} segments={segments} selectedId={selectedId} onSelect={onSelect} />
          <div className="city-temp">
            <div className="city-temp-kicker">{(city?.name ?? "Atlanta").toUpperCase()} — CURRENT</div>
            <div className="city-temp-val">
              {cityTemperatureC != null ? `${cityTemperatureC.toFixed(1)}°C` : "ΔT"}
            </div>
            <div className="city-temp-label">
              {cityTemperatureC != null
                ? "Citywide avg · via FortyGuard API"
                : "Street − city mean · FortyGuard labels"}
            </div>
          </div>
          {!selectedId && <div className="hint">Tap a street marker to inspect it</div>}
          <div className="legend">
            <div className="legend-title">Street risk</div>
            <div className="leg-row">
              <div className="leg-dot" style={{ background: "#E24B4A" }} />
              Hot — hotter than city mean
            </div>
            <div className="leg-row">
              <div className="leg-dot" style={{ background: "#EF9F27" }} />
              Average — near city mean
            </div>
            <div className="leg-row">
              <div className="leg-dot" style={{ background: "#639922" }} />
              Cool — cooler than city mean
            </div>
          </div>
        </div>
        <aside className="detail">
          <StreetCard
            selected={selected}
            recommendation={selectedRec}
            cityTemperatureC={cityTemperatureC}
            cityLabel={cityLabel}
            streetName={streetName}
            streetNameLoading={streetNameLoading}
            fortyguardConfigured={Boolean(capabilities?.fortyguard)}
            forecastLoading={forecastLoading}
            onClose={() => setSelectedId(null)}
          />
        </aside>
      </div>
    </div>
  );
}
