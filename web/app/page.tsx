"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { getCities, getHealth, getRecommendations, getSegments } from "@/lib/api";
import type { Capabilities, City, RecommendItem, Segment } from "@/lib/types";
import SidePanel from "@/components/SidePanel";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

export default function HomePage() {
  const [cities, setCities] = useState<City[]>([]);
  const [cityId, setCityId] = useState("phoenix");
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendItem[]>([]);
  const [recommendError, setRecommendError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getHealth(), getCities()])
      .then(([health, list]) => {
        if (cancelled) return;
        setCapabilities(health.capabilities);
        setCities(list);
        if (list.length && !list.some((c) => c.id === cityId)) {
          setCityId(list[0].id);
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
      />
      <MapView city={city} segments={segments} selectedId={selectedId} onSelect={onSelect} />
    </div>
  );
}
