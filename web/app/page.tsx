"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { getCities, getForecast, getHealth, getRecommendations, getSegments } from "@/lib/api";
import type { Capabilities, City, RecommendItem, Segment } from "@/lib/types";
import SidePanel from "@/components/SidePanel";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

function lagTimestamp(hour: number): string {
  const day = new Date();
  day.setUTCDate(day.getUTCDate() - 7);
  day.setUTCHours(hour, 0, 0, 0);
  return day.toISOString();
}

export default function HomePage() {
  const [cities, setCities] = useState<City[]>([]);
  const [cityId, setCityId] = useState("atlanta");
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendItem[]>([]);
  const [recommendError, setRecommendError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [forecastHour, setForecastHour] = useState(14);
  const [cityTemperatureC, setCityTemperatureC] = useState<number | null>(null);
  const [forecastError, setForecastError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getHealth(), getCities()])
      .then(([health, list]) => {
        if (cancelled) return;
        setCapabilities(health.capabilities);
        setCities(list);
        if (list.length && !list.some((c) => c.id === cityId)) {
          const prefer = list.find((c) => c.id === "atlanta") ?? list[0];
          setCityId(prefer.id);
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
    setRecommendError(null);
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
      .catch((error: Error) => {
        if (!cancelled) {
          setRecommendations([]);
          setRecommendError(error.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [cityId]);

  useEffect(() => {
    if (!capabilities?.fortyguard) {
      setCityTemperatureC(null);
      setForecastError("Live city forecast needs a FortyGuard key.");
      return;
    }
    let cancelled = false;
    const handle = window.setTimeout(() => {
      getForecast(cityId, lagTimestamp(forecastHour))
        .then((body) => {
          if (cancelled) return;
          const point = body.points[0];
          setCityTemperatureC(point ? point.temperature_c : null);
          setForecastError(point ? null : "FortyGuard returned no city temperature for this hour.");
        })
        .catch((error: Error) => {
          if (cancelled) return;
          setCityTemperatureC(null);
          setForecastError(error.message);
        });
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [cityId, forecastHour, capabilities]);

  const selected = useMemo(
    () => segments.find((row) => row.image_id === selectedId) ?? null,
    [segments, selectedId]
  );
  const city = cities.find((row) => row.id === cityId) ?? null;
  const onSelect = useCallback((id: string) => setSelectedId(id), []);

  return (
    <div className="shell">
      <SidePanel
        cities={cities}
        cityId={cityId}
        onCity={setCityId}
        capabilities={capabilities}
        segments={segments}
        selected={selected}
        recommendations={recommendations}
        recommendError={recommendError}
        loadError={loadError}
        forecastHour={forecastHour}
        onForecastHour={setForecastHour}
        cityTemperatureC={cityTemperatureC}
        forecastError={forecastError}
        onSelect={onSelect}
      />
      <MapView city={city} segments={segments} selectedId={selectedId} onSelect={onSelect} />
    </div>
  );
}
