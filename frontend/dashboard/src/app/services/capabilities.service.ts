import {
  Injectable,
  computed,
  inject,
  signal,
  EnvironmentInjector,
  runInInjectionContext,
} from '@angular/core';
import { httpResource, HttpResourceRef } from '@angular/common/http';
import { SensorCapability } from '../models/api.models';
import { API_BASE_URL } from './api.service';

export interface MetricOption {
  id: string;
  label: string;
  unit: string;
  rawUnit: string;
  color: string;
  cssVar: string;
}

/**
 * 10 distinct, vibrant colors assigned to metrics alphabetically.
 */
export const METRIC_PALETTE: readonly string[] = [
  '#2DD4BF', // 0: Teal
  '#38BDF8', // 1: Sky Blue
  '#FBBF24', // 2: Amber
  '#A78BFA', // 3: Purple
  '#F472B6', // 4: Pink
  '#34D399', // 5: Emerald
  '#FB923C', // 6: Orange
  '#818CF8', // 7: Indigo
  '#E879F9', // 8: Fuchsia
  '#22D3EE', // 9: Cyan
];

/**
 * Assigns colors from METRIC_PALETTE to metric keys in alphabetical order,
 * ensuring consistent colors across refreshes as long as capabilities count/names match.
 */
export function assignMetricColors(metricKeys: string[]): Map<string, string> {
  const sorted = Array.from(new Set(metricKeys)).sort((a, b) => a.localeCompare(b));
  const colorMap = new Map<string, string>();
  sorted.forEach((key, index) => {
    colorMap.set(key, METRIC_PALETTE[index % METRIC_PALETTE.length]);
  });
  return colorMap;
}

/**
 * Returns a color for a metric key based on alphabetical position among allKeys.
 * If allKeys is not provided, uses a deterministic string hash across METRIC_PALETTE.
 */
export function getMetricColor(
  key: string,
  allKeys?: string[]
): { color: string; cssVar: string } {
  if (allKeys && allKeys.length > 0) {
    const sorted = Array.from(new Set(allKeys)).sort((a, b) => a.localeCompare(b));
    const idx = sorted.indexOf(key);
    if (idx !== -1) {
      return {
        color: METRIC_PALETTE[idx % METRIC_PALETTE.length],
        cssVar: '--accent',
      };
    }
  }

  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash << 5) - hash + key.charCodeAt(i);
    hash |= 0;
  }
  const color = METRIC_PALETTE[Math.abs(hash) % METRIC_PALETTE.length];
  return { color, cssVar: '--accent' };
}

/**
 * Converts SenML standard units to friendly display units;
 * unknown units pass through as-is.
 */
export function formatDisplayUnit(rawUnit: string): string {
  if (!rawUnit) return '';
  if (rawUnit === 'Cel') return '°C';
  if (rawUnit === '%RH') return '%';
  return rawUnit;
}

/**
 * Normalizes legacy key aliases to canonical keys if needed.
 */
export function normalizeMetricKey(key: string): string {
  if (!key) return '';
  if (key === 'temp') return 'temperature';
  if (key === 'hum') return 'humidity';
  if (key === 'light_pct') return 'light';
  return key;
}

/**
 * Formats any metric key into a readable label (e.g. "air_quality" -> "Air Quality", "pressure" -> "Pressure").
 * Completely agnostic to metric type.
 */
export function formatMetricLabel(key: string): string {
  if (!key) return '';
  return key
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .split(' ')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Creates a default metric configuration dynamically using METRIC_PALETTE.
 * Never hardcodes fixed fallback colors.
 */
export function createDefaultMetricConfig(key: string, allKeys?: string[]): MetricOption {
  const { color, cssVar } = getMetricColor(key, allKeys);
  return {
    id: key,
    label: formatMetricLabel(key),
    unit: '',
    rawUnit: '',
    color,
    cssVar,
  };
}

/**
 * Resolves a MetricOption for a selected metric key from available metric options,
 * handling legacy aliases and falling back dynamically to METRIC_PALETTE.
 */
export function resolveMetricConfig(
  metrics: MetricOption[],
  selectedKey: string
): MetricOption {
  if (!selectedKey) {
    return metrics[0] ?? createDefaultMetricConfig('');
  }
  const norm = normalizeMetricKey(selectedKey);
  const found = metrics.find(
    (m) => m.id === selectedKey || normalizeMetricKey(m.id) === norm
  );
  if (found) {
    return found;
  }
  if (metrics.length > 0) {
    return metrics[0];
  }
  return createDefaultMetricConfig(selectedKey);
}

@Injectable({
  providedIn: 'root',
})
export class CapabilitiesService {
  private readonly baseUrl = inject(API_BASE_URL);
  private readonly injector = inject(EnvironmentInjector);

  private capabilitiesResource: HttpResourceRef<SensorCapability[]> | null = null;
  private readonly _manualCapabilities = signal<SensorCapability[] | null>(null);

  /**
   * Initializes the capabilities HTTP resource using httpResource.
   */
  init(): HttpResourceRef<SensorCapability[]> {
    if (!this.capabilitiesResource) {
      runInInjectionContext(this.injector, () => {
        this.capabilitiesResource = httpResource<SensorCapability[]>(
          () => `${this.baseUrl}/capabilities`,
          { defaultValue: [] }
        );
      });
    }
    return this.capabilitiesResource!;
  }

  get resource(): HttpResourceRef<SensorCapability[]> | null {
    return this.capabilitiesResource;
  }

  readonly capabilities = computed<SensorCapability[]>(() => {
    const manual = this._manualCapabilities();
    if (manual !== null) {
      return manual;
    }
    return this.capabilitiesResource?.value() ?? [];
  });

  readonly isLoading = computed<boolean>(() => {
    if (this._manualCapabilities() !== null) {
      return false;
    }
    return this.capabilitiesResource?.isLoading() ?? false;
  });

  /**
   * Fully agnostic metric list derived from registered capabilities.
   * Colors are assigned alphabetically so order is stable across refreshes.
   * Does not have predefined values for any metric type.
   */
  readonly metrics = computed<MetricOption[]>(() => {
    const caps = this.capabilities();
    if (caps.length === 0) {
      return [];
    }

    const allKeys = caps.map((c) => c.key);
    const colorMap = assignMetricColors(allKeys);

    return caps.map((c) => {
      const color = colorMap.get(c.key) ?? METRIC_PALETTE[0];
      return {
        id: c.key,
        label: formatMetricLabel(c.key),
        unit: formatDisplayUnit(c.unit),
        rawUnit: c.unit,
        color,
        cssVar: '--accent',
      };
    });
  });

  /**
   * Resolves the current metric configuration for a given metric key.
   * Centralizes metric lookup and dynamic palette resolution so components
   * don't duplicate calculation or hardcode fallback colors.
   */
  getMetricConfig(metricKey: string): MetricOption {
    return resolveMetricConfig(this.metrics(), metricKey);
  }

  /**
   * Helper to manually seed capabilities (e.g. for testing).
   */
  setCapabilities(caps: SensorCapability[]): void {
    this._manualCapabilities.set(caps);
  }
}
