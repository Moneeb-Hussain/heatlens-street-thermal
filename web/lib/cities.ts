import type { City } from "./types";

export const DEMO_CITY_IDS = ["atlanta", "chicago"] as const;

export function sortCities(cities: City[]): City[] {
  const rank = new Map(DEMO_CITY_IDS.map((id, index) => [id, index]));
  return cities
    .filter((city) => rank.has(city.id))
    .sort((a, b) => (rank.get(a.id) ?? 99) - (rank.get(b.id) ?? 99));
}
