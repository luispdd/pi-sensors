/**
 * Backend API Payload Models & Data Contracts
 * Matching controller/backend/api.py and controller/backend/db.py
 */

// Sync & Poller Status Constants
export const SYNC_STATUS_OK = 'OK';
export const SYNC_STATUS_OFFLINE = 'OFFLINE';
export const SYNC_STATUS_IDLE = 'IDLE';
export const SYNC_STATUS_ERROR = 'ERROR';
export const SYNC_STATUS_PARTIAL = 'PARTIAL';
export const SYNC_STATUS_BUSY = 'BUSY';

export const SYNC_TIME_NEVER = 'Never';

// Metric Key Constants
export const METRIC_TEMPERATURE = 'temperature';
export const METRIC_TEMP = 'temp';
export const METRIC_HUMIDITY = 'humidity';
export const METRIC_LIGHT = 'light_pct';

export interface Node {
  device_id: string;
  ip_address: string;
  capabilities: string[];
  last_seen: string;
}

export type MeshNode = Node;

export interface PollerStatus {
  last_sync: string | null;
  last_result: Record<string, unknown> | null;
  interval_s: number;
}

export interface SyncState {
  logger_id: string;
  last_cursor: string;
  last_synced_at: string;
}

export interface DatabaseStats {
  total_readings: number;
  total_nodes: number;
  sync_states: SyncState[];
}

export interface SystemStatus {
  device_id: string;
  device_type: string;
  status: string;
  uptime_s: number;
  poller: PollerStatus;
  database: DatabaseStats;
}

export type Status = SystemStatus;

export interface SensorMetrics {
  temp?: number;
  temperature?: number;
  humidity?: number;
  light_pct?: number;
  [key: string]: unknown;
}

export interface Reading {
  id: number;
  timestamp: string;
  device_id: string;
  metrics: SensorMetrics;
  ingested_at: string;
}

export interface ReadingsQueryParams {
  device_id?: string;
  since?: string;
  until?: string;
  limit?: number;
}

export interface DisplayMessageRequest {
  target: string;
  message: string;
}

export interface DisplayMessageResponse {
  status: 'success' | 'failed' | 'error' | string;
  target?: string;
  ip_address?: string;
  message?: string;
  error?: string;
}

export interface DiscoverResponse {
  discovered_count: number;
  nodes: Node[];
}

export interface SyncResponse {
  status: string;
  [key: string]: unknown;
}
