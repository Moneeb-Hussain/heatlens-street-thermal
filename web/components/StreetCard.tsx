"use client";

import { useState } from "react";
import type { Segment } from "@/lib/types";

type Tab = "temp" | "feat" | "rec";

type Props = {
  selected: Segment | null;
  canopyBeta: number | null;
  targetCanopy: number;
  cityTemperatureC: number | null;
  cityLabel: string;
  streetName: string | null;
  streetNameLoading: boolean;
  fortyguardConfigured: boolean;
  forecastLoading: boolean;
  onClose: () => void;
};

function pct(value: number): number {
  return Math.round(value * 100);
}

function riskLabel(delta: number): string {
  if (delta > 0.6) return "Hotter than city mean";
  if (delta < 0) return "Below city average";
  return "Near city average";
}

function deltaColor(delta: number): string {
  if (delta > 0.4) return "#E24B4A";
  if (delta < 0) return "#639922";
  return "#EF9F27";
}

function indicativeCoolingC(canopyFrac: number, beta: number | null, target: number): number | null {
  if (beta == null || beta >= 0) return null;
  return -beta * Math.max(target - canopyFrac, 0);
}

export default function StreetCard({
  selected,
  canopyBeta,
  targetCanopy,
  cityTemperatureC,
  cityLabel,
  streetName,
  streetNameLoading,
  fortyguardConfigured,
  forecastLoading,
  onClose,
}: Props) {
  const [tab, setTab] = useState<Tab>("temp");

  if (!selected) {
    return (
      <div className="empty-state">
        <div className="empty-marks" aria-hidden>
          <span className="empty-mark" style={{ background: "#E24B4A" }} />
          <span className="empty-mark" style={{ background: "#EF9F27" }} />
          <span className="empty-mark" style={{ background: "#639922" }} />
        </div>
        <div className="empty-title">Select a street to inspect heat</div>
        <p className="empty-copy">
          See how hot it runs versus the city, what the street is made of, and where extra
          canopy would cool it most.
        </p>
      </div>
    );
  }

  const predicted = cityTemperatureC != null ? cityTemperatureC + selected.delta_t : null;
  const cooling = indicativeCoolingC(selected.features.canopy_frac, canopyBeta, targetCanopy);
  const coolingLabel = cooling == null ? null : `${cooling.toFixed(1)}°C`;
  const canopyPct = pct(selected.features.canopy_frac);
  const targetPct = pct(targetCanopy);
  const plant = cooling != null && cooling > 0.2;
  const fallbackId = selected.block_id && !selected.block_id.startsWith("b_")
    ? selected.block_id
    : null;
  const title = streetNameLoading
    ? "Locating street…"
    : streetName || fallbackId || "Unnamed street";
  const feats = [
    { name: "Asphalt", value: selected.features.asphalt_frac, color: "#888780" },
    { name: "Open sky", value: selected.features.sky_frac, color: "#85B7EB" },
    { name: "Tree cover", value: selected.features.canopy_frac, color: "#639922" },
    { name: "Buildings", value: selected.features.building_frac, color: "#B4B2A9" },
  ];

  return (
    <div className="street-content">
      <div className="street-info">
        <div>
          <div className="street-name">{title}</div>
          <div className="street-meta">{cityLabel}</div>
        </div>
        <button type="button" className="close-x" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      <div className="tab-bar">
        {(
          [
            ["temp", "Temperature"],
            ["feat", "Urban Form"],
            ["rec", "Action"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`tab${tab === id ? " act" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "temp" && (
        <div>
          <div className="temp-row">
            <div className="tcard">
              <div className="tcard-label">Predicted temp</div>
              <div className="tcard-val" style={{ color: predicted == null ? undefined : "#E24B4A" }}>
                {predicted == null ? "—" : `${predicted.toFixed(1)}°C`}
              </div>
              <div className="tcard-sub">
                {predicted == null
                  ? forecastLoading
                    ? "Loading FortyGuard city °C"
                    : fortyguardConfigured
                      ? "City °C unavailable — ΔT still real"
                      : "Needs FortyGuard city °C + ΔT"
                  : "City snapshot + street ΔT"}
              </div>
            </div>
            <div className="tcard">
              <div className="tcard-label">Vs. city average</div>
              <div className="tcard-val" style={{ color: deltaColor(selected.delta_t) }}>
                {selected.delta_t >= 0 ? "+" : ""}
                {selected.delta_t.toFixed(1)}°C
              </div>
              <div className="tcard-sub">
                {cityTemperatureC != null
                  ? `city avg ${cityTemperatureC.toFixed(1)}°C`
                  : riskLabel(selected.delta_t)}
              </div>
            </div>
          </div>
          <div className="forecast-section">
            <div className="fc-head">
              <div className="section-label" style={{ marginBottom: 0 }}>
                City snapshot
              </div>
              <span className="fc-src">FortyGuard heatmap API</span>
            </div>
            {cityTemperatureC != null ? (
              <div className="tcard-val" style={{ color: "#E24B4A", marginTop: 10 }}>
                {cityTemperatureC.toFixed(1)}°C
              </div>
            ) : (
              <p className="muted" style={{ marginTop: 10 }}>
                {forecastLoading
                  ? "Loading citywide °C…"
                  : fortyguardConfigured
                    ? "Could not read city °C. Street ΔT on the map is still real."
                    : "Key not set — map still shows labelled street ΔT."}
              </p>
            )}
            <p className="tcard-sub" style={{ marginTop: 6 }}>
              One lagged citywide mean. Hourly bars are not invented.
            </p>
          </div>
        </div>
      )}

      {tab === "feat" && (
        <div className="feat-section">
          <div className="section-label">What this street looks like</div>
          {feats.map((row) => (
            <div className="feat-row" key={row.name}>
              <span className="feat-name">{row.name}</span>
              <div className="feat-track">
                <div
                  className="feat-fill"
                  style={{ width: `${pct(row.value)}%`, background: row.color }}
                />
              </div>
              <span className="feat-pct">{pct(row.value)}%</span>
            </div>
          ))}
        </div>
      )}

      {tab === "rec" && (
        <div className="rec-section">
          <div className="section-label">Recommended action</div>
          <div
            className="rec-card"
            style={
              plant
                ? { background: "var(--bg-danger)", color: "var(--text-danger)" }
                : { background: "var(--bg-success)", color: "var(--text-success)" }
            }
          >
            <div className="rec-card-title">
              {plant ? "Plant street trees" : cooling != null ? "Lower planting priority" : "Ranking unavailable"}
            </div>
            <div className="rec-card-body">
              {plant && coolingLabel
                ? `Tree cover is ${canopyPct}% (target ${targetPct}%). Indicative cooling if canopy rises toward ${targetPct}%: about ${coolingLabel}. Not a causal guarantee.`
                : coolingLabel
                  ? `Tree cover is ${canopyPct}% (target ${targetPct}%). Extra canopy here is only ~${coolingLabel}.`
                  : `Tree cover is ${canopyPct}%. Fitted canopy coefficient is missing, so this street is not ranked.`}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
