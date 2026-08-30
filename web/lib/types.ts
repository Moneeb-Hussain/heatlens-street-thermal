export type CityRole = "train" | "holdout" | "transfer";

export type City = {
  id: string;
  name: string;
  role: CityRole;
  timezone: string;
  coverage_validated: boolean;
  center_lat: number;
  center_lon: number;
  bbox: { west: number; south: number; east: number; north: number };
};

export type UrbanFormFeatures = {
  canopy_frac: number;
  asphalt_frac: number;
  sky_frac: number;
  building_frac: number;
};

export type Segment = {
  image_id: string;
  lat: number;
  lon: number;
  city: string;
  block_id: string;
  delta_t: number;
  split: string;
  source: string;
  validated: boolean;
  features: UrbanFormFeatures;
};

export type Capabilities = {
  segments: boolean;
  fortyguard: boolean;
  mapillary: boolean;
  coefficients: boolean;
  model: boolean;
  model_name: string | null;
};

export type Health = {
  status: string;
  version: string;
  capabilities: Capabilities;
};

export type ApiError = {
  error: boolean;
  code: string;
  message: string;
};

export type RecommendItem = {
  image_id: string;
  lat: number;
  lon: number;
  current_delta_t: number;
  current_canopy_frac: number;
  target_canopy_frac: number;
  estimated_delta_t: number;
  estimated_cooling_c: number;
  indicative: boolean;
  validated: boolean;
};

export type ForecastPoint = {
  timestamp: string;
  temperature_c: number;
};

export type Forecast = {
  city: string;
  source: string;
  points: ForecastPoint[];
};

export type ValidatePair = {
  image_id: string;
  predicted_delta_t: number | null;
  reference_delta_t: number;
  validated: boolean;
};

export type ValidateView = {
  city: string;
  count: number;
  pairs: ValidatePair[];
};
