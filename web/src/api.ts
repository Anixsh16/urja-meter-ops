export type Meta = { fetched_at: string; cache: string; age_seconds: number; warnings: string[] };
export type Result<T> = { data: T; meta: Meta };
export type Segment = { level: string; code: string | null; name: string | null };
export type Meter = {
  id: string; serial_number: string | null; manufacturer: string | null; phase: string | null;
  status: string | null; installation_type: string | null; portal_build: string | null;
  transformer_code: string | null; location: { latitude: number; longitude: number } | null;
  hierarchy: Segment[]; warnings: string[];
};
export type MeterPage = { items: Meter[]; total: number; page: number; page_size: number; total_pages: number };
export type NetworkNode = { id: string; parent_id: string | null; level: string; code: string | null;
  name: string; aliases: string[]; meter_count: number; child_count: number; warnings: string[] };
export type NodePage = { items: NetworkNode[]; total: number };
export type Reading = { timestamp: string; source_timestamp: string; kwh: string | null; kvah: string | null; voltage_r: string | null };
export type Consumption = { meter_id: string; kind: string; timezone: string; timezone_basis: string; readings: Reading[] };

export class ApiError extends Error {
  constructor(message: string, public status: number, public requestId?: string) { super(message); }
}

export async function get<T>(path: string, token: string, signal?: AbortSignal): Promise<Result<T>> {
  const response = await fetch(`/api/v1${path}`, { headers: { Authorization: `Bearer ${token}` }, signal });
  let body;
  try { body = await response.json(); } catch { throw new ApiError('The service returned an unexpected response. Please retry.', response.status); }
  if (!response.ok) throw new ApiError(body.error?.message ?? 'The request could not be completed.', response.status, body.error?.request_id);
  return body;
}

export function queryString(values: Record<string, string | number | undefined>) {
  return new URLSearchParams(Object.entries(values).filter(([, value]) => value !== undefined && value !== '').map(([key, value]) => [key, String(value)])).toString();
}

export const number = (value: string | number | null | undefined, digits = 2) => value == null ? '—' : Number(value).toLocaleString('en-IN', { maximumFractionDigits: digits });
