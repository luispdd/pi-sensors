import { Reading, SensorMetrics } from '../../models/api.models';
import {
  METRIC_PALETTE,
  assignMetricColors,
  getMetricColor,
  normalizeMetricKey,
  resolveMetricConfig,
  createDefaultMetricConfig,
} from '../../services/capabilities.service';

export {
  METRIC_PALETTE,
  assignMetricColors,
  getMetricColor,
  resolveMetricConfig,
  createDefaultMetricConfig,
};

export const BOARD_PALETTE: readonly string[] = METRIC_PALETTE;

export function getBoardColor(index: number): string {
  return BOARD_PALETTE[index % BOARD_PALETTE.length];
}

export interface ChartPoint {
  x: number;
  y: number;
}

const COMMON_ALIASES: Record<string, string[]> = {
  temperature: ['temp'],
  temp: ['temperature'],
  humidity: ['hum'],
  hum: ['humidity'],
  light: ['light_pct'],
  light_pct: ['light'],
};

/**
 * Extracts a numeric metric value from a reading's metrics dictionary in a
 * metric-agnostic way. Checks direct match first, then known legacy aliases,
 * then case-insensitive match for arbitrary/unknown metrics.
 */
export function extractMetricValue(
  metrics: SensorMetrics | Record<string, unknown> | undefined,
  metricKey: string
): number | undefined {
  if (!metrics || typeof metrics !== 'object' || !metricKey) {
    return undefined;
  }

  // 1. Direct match on the exact metric key
  let val: unknown = metrics[metricKey];

  // 2. Check legacy aliases if direct match wasn't present
  if (val === undefined) {
    const aliases = COMMON_ALIASES[metricKey];
    if (aliases) {
      for (const alias of aliases) {
        if (metrics[alias] !== undefined) {
          val = metrics[alias];
          break;
        }
      }
    }
  }

  // 3. Case-insensitive fallback for arbitrary/unknown metrics
  if (val === undefined) {
    const lowerKey = metricKey.toLowerCase();
    for (const [k, v] of Object.entries(metrics)) {
      if (k.toLowerCase() === lowerKey) {
        val = v;
        break;
      }
    }
  }

  if (typeof val === 'number' && !isNaN(val) && isFinite(val)) {
    return Math.round(val * 10) / 10;
  }

  return undefined;
}

/**
 * Groups readings by device_id into a Map of sorted chronological {x, y} points
 * for any metric key, completely agnostic to metric type.
 */
export function groupByDevice(
  readings: Reading[],
  metricKey: string
): Map<string, ChartPoint[]> {
  const result = new Map<string, ChartPoint[]>();
  if (!readings || readings.length === 0 || !metricKey) {
    return result;
  }

  // Intermediate map: device_id -> Map<timeMs, { sum, count }>
  const deviceTimeMap = new Map<string, Map<number, { sum: number; count: number }>>();

  for (const r of readings) {
    if (!r) continue;
    const deviceId = r.device_id || 'unknown';
    const val = extractMetricValue(r.metrics, metricKey);
    if (val === undefined) continue;

    const timeMs = new Date(r.timestamp).getTime();
    if (isNaN(timeMs)) continue;

    let timeMap = deviceTimeMap.get(deviceId);
    if (!timeMap) {
      timeMap = new Map<number, { sum: number; count: number }>();
      deviceTimeMap.set(deviceId, timeMap);
    }

    const entry = timeMap.get(timeMs);
    if (entry) {
      entry.sum += val;
      entry.count++;
    } else {
      timeMap.set(timeMs, { sum: val, count: 1 });
    }
  }

  for (const [deviceId, timeMap] of deviceTimeMap.entries()) {
    const points: ChartPoint[] = [];
    for (const [x, { sum, count }] of timeMap.entries()) {
      points.push({
        x,
        y: Math.round((sum / count) * 10) / 10,
      });
    }
    points.sort((a, b) => a.x - b.x);
    if (points.length > 0) {
      result.set(deviceId, points);
    }
  }

  return result;
}
