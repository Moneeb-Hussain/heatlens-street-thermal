import type { City } from "./types";

export const CITY_ORDER = [
  "atlanta",
  "chicago",
  "phoenix",
  "houston",
  "miami",
  "karachi",
  "lahore",
];

export function sortCities(cities: City[]): City[] {
  return [...cities].sort((a, b) => {
    const ia = CITY_ORDER.indexOf(a.id);
    const ib = CITY_ORDER.indexOf(b.id);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}
