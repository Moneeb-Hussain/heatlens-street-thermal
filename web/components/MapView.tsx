"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { City, Segment } from "@/lib/types";

type Props = {
  city: City | null;
  segments: Segment[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function colorForDelta(delta: number): string {
  if (delta <= 0) {
    const u = Math.min(1, Math.abs(delta) / 2.4);
    return lerp("#EF9F27", "#639922", u);
  }
  const u = Math.min(1, delta / 1.15);
  return lerp("#EF9F27", "#E24B4A", u);
}

function lerp(a: string, b: string, t: number): string {
  const pa = hex(a);
  const pb = hex(b);
  const m = (i: number) => Math.round(pa[i] + (pb[i] - pa[i]) * t);
  return `rgb(${m(0)}, ${m(1)}, ${m(2)})`;
}

function hex(value: string): [number, number, number] {
  const n = value.replace("#", "");
  return [
    parseInt(n.slice(0, 2), 16),
    parseInt(n.slice(2, 4), 16),
    parseInt(n.slice(4, 6), 16),
  ];
}

export default function MapView({ city, segments, selectedId, onSelect }: Props) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    if (!rootRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: rootRef.current,
      style: "https://tiles.openfreemap.org/styles/positron",
      center: city ? [city.center_lon, city.center_lat] : [-84.388, 33.749],
      zoom: 13.2,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !city) return;
    map.flyTo({ center: [city.center_lon, city.center_lat], zoom: 13.2, essential: true });
  }, [city]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = segments.map((segment) => {
      const on = selectedId === segment.image_id;
      const el = document.createElement("button");
      el.type = "button";
      el.setAttribute("aria-label", `Street ${segment.image_id}`);
      el.style.width = on ? "16px" : "12px";
      el.style.height = el.style.width;
      el.style.borderRadius = "50%";
      el.style.border = "2.5px solid white";
      el.style.boxShadow = on
        ? "0 0 0 4px rgba(255,255,255,0.5), 0 2px 8px rgba(0,0,0,0.3)"
        : "0 1px 4px rgba(0,0,0,0.25)";
      el.style.padding = "0";
      el.style.background = colorForDelta(segment.delta_t);
      el.style.cursor = "pointer";
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([segment.lon, segment.lat])
        .addTo(map);
      el.addEventListener("click", () => onSelect(segment.image_id));
      return marker;
    });
  }, [segments, selectedId, onSelect]);

  return <div ref={rootRef} className="map-root" />;
}
