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
  const t = Math.max(-6, Math.min(6, delta));
  if (t <= 0) {
    const u = (t + 6) / 6;
    return lerp("#3d7ea6", "#d9d0c3", u);
  }
  return lerp("#d9d0c3", "#d4531a", t / 6);
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
      style: {
        version: 8,
        sources: {
          carto: {
            type: "raster",
            tiles: [
              "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
            ],
            tileSize: 256,
            attribution: "© OpenStreetMap © CARTO",
          },
        },
        layers: [{ id: "carto", type: "raster", source: "carto" }],
      },
      center: city ? [city.center_lon, city.center_lat] : [-112.074, 33.4484],
      zoom: 13,
      attributionControl: true,
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
    map.flyTo({ center: [city.center_lon, city.center_lat], zoom: 13, essential: true });
  }, [city]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = segments.map((segment) => {
      const el = document.createElement("button");
      el.type = "button";
      el.setAttribute("aria-label", `Street ${segment.image_id}`);
      el.style.width = selectedId === segment.image_id ? "16px" : "10px";
      el.style.height = el.style.width;
      el.style.borderRadius = "50%";
      el.style.border = "1px solid #14110e";
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

  return (
    <div className="map-wrap">
      <div ref={rootRef} className="map-root" />
      <div className="legend">
        Cooler than city mean
        <div className="legend-bar" />
        Hotter than city mean · ΔT °C
      </div>
    </div>
  );
}
