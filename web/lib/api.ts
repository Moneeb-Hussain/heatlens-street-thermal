import type {
  ApiError,
  City,
  Forecast,
  Health,
  RecommendItem,
  Segment,
  ValidateView,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = body as ApiError;
    throw new Error(err.message || `Request failed (${response.status})`);
  }
  return body as T;
}

export async function getHealth(): Promise<Health> {
  return request("/health");
}

export async function getCities(): Promise<City[]> {
  const body = await request<{ cities: City[] }>("/cities");
  return body.cities;
}

export async function getSegments(city: string): Promise<Segment[]> {
  const body = await request<{ city: string; count: number; segments: Segment[] }>(
    `/segments?city=${encodeURIComponent(city)}`
  );
  return body.segments;
}

export async function getRecommendations(city: string): Promise<RecommendItem[]> {
  const body = await request<{ items: RecommendItem[] }>(
    `/recommend?city=${encodeURIComponent(city)}&limit=80`
  );
  return body.items;
}

export async function getForecast(city: string, timestamp?: string): Promise<Forecast> {
  const query = timestamp
    ? `/forecast?city=${encodeURIComponent(city)}&timestamp=${encodeURIComponent(timestamp)}`
    : `/forecast?city=${encodeURIComponent(city)}`;
  return request<Forecast>(query);
}

export async function getValidate(city: string): Promise<ValidateView> {
  return request<ValidateView>(`/validate?city=${encodeURIComponent(city)}`);
}

export async function getStreetName(lat: number, lon: number): Promise<string | null> {
  const body = await request<{ street: string | null }>(
    `/street-name?lat=${encodeURIComponent(String(lat))}&lon=${encodeURIComponent(String(lon))}`
  );
  return body.street;
}
