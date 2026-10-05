import { Component, computed, DestroyRef, effect, inject, signal } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChartComponent } from 'ng-apexcharts';
import {
  ApexAxisChartSeries,
} from 'ng-apexcharts';
import { ApiService } from '../../services/api.service';
import { WebSocketService } from '../../services/websocket.service';
import { Node, Reading } from '../../models/api.models';

import {
  BOARD_PALETTE,
  extractMetricValue,
  groupByDevice,
} from '../../shared/utils/chart.utils';

export const METRIC_TEMPERATURE = 'temperature';
export const METRIC_HUMIDITY = 'humidity';
export const METRIC_LIGHT = 'light_pct';

export type MetricType =
  | typeof METRIC_TEMPERATURE
  | typeof METRIC_HUMIDITY
  | typeof METRIC_LIGHT;

export const NODE_ALL = 'all';
export const RANGE_ALL = 'all';

export interface BoardStat {
  device_id: string;
  min: number | null;
  max: number | null;
  avg: number | null;
  latest: number | null;
  color?: string;
}

export interface MetricConfig {
  id: MetricType;
  label: string;
  unit: string;
  cssVar: string;
  color: string;
  textClass: string;
}

export const METRIC_CONFIGS: Record<MetricType, MetricConfig> = {
  [METRIC_TEMPERATURE]: {
    id: METRIC_TEMPERATURE,
    label: 'Temperature',
    unit: '°C',
    cssVar: '--metric-temperature',
    color: '#2DD4BF',
    textClass: 'text-metric-temperature',
  },
  [METRIC_HUMIDITY]: {
    id: METRIC_HUMIDITY,
    label: 'Humidity',
    unit: '%',
    cssVar: '--metric-humidity',
    color: '#38BDF8',
    textClass: 'text-metric-humidity',
  },
  [METRIC_LIGHT]: {
    id: METRIC_LIGHT,
    label: 'Light Level',
    unit: '%',
    cssVar: '--metric-light',
    color: '#FBBF24',
    textClass: 'text-metric-light',
  },
};

export interface TimeRangeOption {
  label: string;
  value: string;
  durationMs: number | null;
  days: number | null;
}

export type DayRangeOption = TimeRangeOption;

export const TIME_RANGE_OPTIONS: readonly TimeRangeOption[] = [
  { label: 'Last 10m', value: '10m', durationMs: 10 * 60 * 1000, days: 10 / (24 * 60) },
  { label: 'Last 1h', value: '1h', durationMs: 60 * 60 * 1000, days: 1 / 24 },
  { label: 'Last 3h', value: '3h', durationMs: 3 * 3600 * 1000, days: 3 / 24 },
  { label: 'Last 6h', value: '6h', durationMs: 6 * 3600 * 1000, days: 6 / 24 },
  { label: 'Last 1d', value: '1d', durationMs: 24 * 3600 * 1000, days: 1 },
  { label: 'Last 3d', value: '3d', durationMs: 3 * 24 * 3600 * 1000, days: 3 },
  { label: 'Last 7d', value: '7d', durationMs: 7 * 24 * 3600 * 1000, days: 7 },
  { label: 'Last 14d', value: '14d', durationMs: 14 * 24 * 3600 * 1000, days: 14 },
  { label: 'Last 30d', value: '30d', durationMs: 30 * 24 * 3600 * 1000, days: 30 },
  { label: 'All', value: 'all', durationMs: null, days: null },
] as const;

export const DAY_RANGE_OPTIONS = TIME_RANGE_OPTIONS;

export const GRAPHS_FILTER_STORAGE_KEY = 'pi-sensors:graphs-filter';

export interface GraphsFilterState {
  deviceId: string;
  metric: string;
  timeRange: string;
  regularOnly: boolean;
}

export function findTimeRangeOption(val: string): TimeRangeOption | undefined {
  return TIME_RANGE_OPTIONS.find(
    (o) =>
      o.value.toLowerCase() === val.toLowerCase() ||
      o.value.toLowerCase() === `${val.toLowerCase()}d` ||
      (o.days !== null && String(o.days) === val) ||
      (val.toLowerCase() === 'all' && o.value === 'all')
  );
}

export function getTimeRangeDurationMs(rangeVal: string): number | null {
  const opt = findTimeRangeOption(rangeVal);
  if (opt) {
    return opt.durationMs;
  }
  if (rangeVal.endsWith('m')) {
    const mins = Number(rangeVal.slice(0, -1));
    return isNaN(mins) ? null : mins * 60 * 1000;
  }
  if (rangeVal.endsWith('h')) {
    const hrs = Number(rangeVal.slice(0, -1));
    return isNaN(hrs) ? null : hrs * 3600 * 1000;
  }
  if (rangeVal.endsWith('d')) {
    const days = Number(rangeVal.slice(0, -1));
    return isNaN(days) ? null : days * 86400000;
  }
  return null;
}

import { TopToolbarComponent } from '../../shared/components/top-toolbar/top-toolbar.component';
import { LiveControlsComponent } from '../../shared/components/live-controls/live-controls.component';
import { getThemeColor } from '../../shared/utils/theme.utils';
import { CapabilitiesService, MetricOption } from '../../services/capabilities.service';

@Component({
  selector: 'app-graphs',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    DecimalPipe,
    ChartComponent,
    TopToolbarComponent,
    LiveControlsComponent,
  ],
  templateUrl: './graphs.component.html',
  styleUrl: './graphs.component.scss',
})
export class GraphsComponent {
  private readonly api = inject(ApiService);
  private readonly capabilitiesService = inject(CapabilitiesService);
  private readonly wsService = inject(WebSocketService);
  private readonly destroyRef = inject(DestroyRef);

  readonly NODE_ALL = NODE_ALL;
  readonly RANGE_ALL = RANGE_ALL;
  readonly METRIC_TEMPERATURE = METRIC_TEMPERATURE;
  readonly METRIC_HUMIDITY = METRIC_HUMIDITY;
  readonly METRIC_LIGHT = METRIC_LIGHT;
  readonly metrics = this.capabilitiesService.metrics;
  readonly timeRangeOptions = TIME_RANGE_OPTIONS;
  readonly dayRangeOptions = TIME_RANGE_OPTIONS;

  private readonly savedFilter = this.loadSavedFilters();

  readonly selectedDeviceId = signal<string>(this.savedFilter?.deviceId ?? NODE_ALL);
  readonly selectedMetric = signal<string>(this.savedFilter?.metric ?? METRIC_TEMPERATURE);
  readonly selectedRange = signal<string>(this.savedFilter?.timeRange ?? '7d');
  readonly selectedDays = signal<number | null>(
    this.savedFilter ? (findTimeRangeOption(this.savedFilter.timeRange)?.days ?? null) : 7
  );
  readonly regularOnly = signal<boolean>(this.savedFilter?.regularOnly ?? false);
  readonly liveReadings = signal<Reading[]>([]);

  readonly nodesResource = this.api.getNodes();
  readonly statusResource = this.api.getStatus();
  readonly nodes = computed<Node[]>(() => this.nodesResource.value() ?? []);

  readonly readingsResource = this.api.getReadings(() => {
    const devId = this.selectedDeviceId();
    const durationMs = getTimeRangeDurationMs(this.selectedRange());
    const isFineTuned = this.regularOnly() ? false : undefined;
    const since =
      durationMs !== null
        ? new Date(Date.now() - durationMs).toISOString()
        : undefined;

    return {
      device_id: devId !== NODE_ALL ? devId : undefined,
      since,
      is_fine_tuned: isFineTuned,
    };
  });

  private lastStatusRefreshTime = Date.now();

  constructor() {
    this.api.reloadStatus?.();

    const cadenceTimer = setInterval(() => {
      this.checkCadenceRefresh();
    }, 1000);
    this.destroyRef.onDestroy(() => clearInterval(cadenceTimer));

    const sub = this.wsService.readings$.subscribe((reading) => {
      this.handleIncomingReading(reading);
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());

    effect(() => {
      // Track signals for persistence
      const _dev = this.selectedDeviceId();
      const _met = this.selectedMetric();
      const _range = this.selectedRange();
      const _reg = this.regularOnly();
      this.saveFilters();
    });
  }

  checkCadenceRefresh(now: number = Date.now()): void {
    const statusVal = this.statusResource.value() ?? this.api.cachedStatus?.();
    const syncIntervalMs = (statusVal?.poller?.interval_s ?? 300) * 1000;
    if (now - this.lastStatusRefreshTime >= syncIntervalMs) {
      this.lastStatusRefreshTime = now;
      this.statusResource.reload();
    }
  }

  handleIncomingReading(reading: Reading): void {
    // 1. Regular-only filter check: drop if regularOnly is active and reading is live
    if (this.regularOnly() && reading.is_fine_tuned) {
      return;
    }

    // 2. Matching device check
    const currentDevice = this.selectedDeviceId();
    if (currentDevice !== NODE_ALL && reading.device_id !== currentDevice) {
      return;
    }

    // 3. Matching metric check
    const currentMetric = this.selectedMetric();
    const val = extractMetricValue(reading.metrics, currentMetric);
    if (val === undefined || val === null || isNaN(val)) {
      return;
    }

    // 4. Update or append live point
    this.liveReadings.update((prev) => {
      const idx = prev.findIndex((r) => r.device_id === reading.device_id && r.timestamp === reading.timestamp);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = reading;
        return copy;
      }
      return [...prev, reading];
    });
  }

  readonly allReadings = computed<Reading[]>(() => {
    const fetched = this.readingsResource.value() ?? [];
    const live = this.liveReadings();
    if (live.length === 0) {
      return fetched;
    }
    const isRegularOnly = this.regularOnly();
    const currentDevice = this.selectedDeviceId();

    const map = new Map<string, Reading>();
    for (const r of fetched) {
      map.set(`${r.device_id}:${r.timestamp}`, r);
    }
    for (const r of live) {
      if (isRegularOnly && r.is_fine_tuned) {
        continue;
      }
      if (currentDevice !== NODE_ALL && r.device_id !== currentDevice) {
        continue;
      }
      map.set(`${r.device_id}:${r.timestamp}`, r);
    }
    return Array.from(map.values()).sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  });

  readonly readings = computed<Reading[]>(() => this.allReadings());

  readonly isLoading = computed<boolean>(
    () =>
      this.readingsResource.isLoading() ||
      this.nodesResource.isLoading() ||
      this.statusResource.isLoading()
  );
  readonly hasError = computed(
    () => !!(this.readingsResource.error?.() || this.nodesResource.error?.() || this.statusResource.error?.())
  );
  readonly errorMessage = computed(() => {
    const err = this.readingsResource.error?.() || this.nodesResource.error?.() || this.statusResource.error?.();
    if (!err) return null;
    return typeof err === 'object' && err !== null && 'message' in err
      ? String((err as { message: unknown }).message)
      : 'Failed to load telemetry data from controller. Please verify the backend service is running.';
  });
  readonly currentMetricConfig = computed<MetricOption>(() =>
    this.capabilitiesService.getMetricConfig(this.selectedMetric())
  );

  // Extract numerical values in chronological order
  readonly parsedData = computed(() => {
    const items = [...this.readings()].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    const metric = this.selectedMetric();
    const points: { x: number; y: number; timestamp: string; device_id: string }[] = [];

    for (const r of items) {
      const val = extractMetricValue(r.metrics, metric);
      if (val !== undefined) {
        const timeMs = new Date(r.timestamp).getTime();
        if (!isNaN(timeMs)) {
          points.push({
            x: timeMs,
            y: val,
            timestamp: r.timestamp,
            device_id: r.device_id,
          });
        }
      }
    }

    return points;
  });

  readonly stats = computed(() => {
    const data = this.parsedData();
    if (data.length === 0) {
      return { min: null, max: null, avg: null, latest: null, count: 0 };
    }

    let min = Infinity;
    let max = -Infinity;
    let sum = 0;

    for (const p of data) {
      if (p.y < min) min = p.y;
      if (p.y > max) max = p.y;
      sum += p.y;
    }

    const avg = Math.round((sum / data.length) * 10) / 10;
    const latest = data[data.length - 1].y;

    return {
      min,
      max,
      avg,
      latest,
      count: data.length,
    };
  });

  readonly chartSeries = computed<ApexAxisChartSeries>(() => {
    const readings = this.readings();
    const metric = this.selectedMetric();
    const grouped = groupByDevice(readings, metric);

    if (grouped.size === 0) {
      return [];
    }

    const series: ApexAxisChartSeries = [];
    let idx = 0;
    for (const [deviceId, points] of grouped.entries()) {
      series.push({
        name: deviceId,
        data: points,
        color: BOARD_PALETTE[idx % BOARD_PALETTE.length],
      });
      idx++;
    }

    return series;
  });

  readonly perBoardStats = computed<BoardStat[]>(() => {
    const seriesList = this.chartSeries();
    if (seriesList.length === 0) {
      return [];
    }

    return seriesList.map((series) => {
      const deviceId = String(series.name ?? '');
      const rawData = series.data ?? [];
      const points = rawData as { x: number; y: number }[];

      if (points.length === 0) {
        return {
          device_id: deviceId,
          min: null,
          max: null,
          avg: null,
          latest: null,
          color: (series as { color?: string }).color,
        };
      }

      let min = Infinity;
      let max = -Infinity;
      let sum = 0;

      for (const p of points) {
        const val = p.y;
        if (val < min) min = val;
        if (val > max) max = val;
        sum += val;
      }

      const avg = Math.round((sum / points.length) * 10) / 10;
      const latest = points[points.length - 1].y;

      return {
        device_id: deviceId,
        min: min === Infinity ? null : min,
        max: max === -Infinity ? null : max,
        avg,
        latest,
        color: (series as { color?: string }).color,
      };
    });
  });

  readonly seriesColors = computed<string[]>(() => {
    const series = this.chartSeries();
    if (series.length === 0) {
      return [...BOARD_PALETTE];
    }
    return series.map(
      (s, idx) => (s as { color?: string }).color ?? BOARD_PALETTE[idx % BOARD_PALETTE.length]
    );
  });

  readonly chartOptions = computed(() => {
    const cfg = this.currentMetricConfig();
    const colors = this.seriesColors();
    const textMutedColor = getThemeColor('--text-muted', '#7B8494');
    const borderColor = getThemeColor('--border', 'rgba(255, 255, 255, 0.07)');
    const dividerColor = getThemeColor('--divider', 'rgba(255, 255, 255, 0.06)');

    return {
      chart: {
        type: 'area' as const,
        height: 380,
        background: 'transparent',
        toolbar: {
          show: true,
          tools: {
            download: false,
            selection: true,
            zoom: true,
            zoomin: true,
            zoomout: true,
            pan: true,
            reset: true,
          },
          autoSelected: 'pan' as const,
        },
        zoom: {
          enabled: true,
          type: 'x' as const,
          autoScaleYaxis: true,
          allowMouseWheelZoom: false,
        },
        animations: {
          enabled: true,
        },
      },
      colors,
      fill: {
        type: 'gradient' as const,
        gradient: {
          shadeIntensity: 1,
          opacityFrom: 0.4,
          opacityTo: 0.05,
          stops: [0, 95, 100],
        },
      },
      stroke: {
        show: true,
        curve: 'smooth' as const,
        width: 3,
        colors,
      },
      markers: {
        size: 4,
        colors,
        strokeColors: '#0B0D12',
        strokeWidth: 2,
        hover: {
          size: 7,
        },
      },
      legend: {
        show: true,
        position: 'bottom' as const,
        horizontalAlign: 'center' as const,
        labels: {
          colors: textMutedColor,
        },
        itemMargin: {
          horizontal: 12,
          vertical: 8,
        },
      },
      dataLabels: {
        enabled: false,
      },
      xaxis: {
        type: 'datetime' as const,
        labels: {
          style: {
            colors: textMutedColor,
            fontSize: '11px',
          },
          datetimeUTC: false,
          format: 'HH:mm',
        },
        axisBorder: {
          color: borderColor,
        },
        axisTicks: {
          color: borderColor,
        },
      },
      yaxis: {
        labels: {
          style: {
            colors: textMutedColor,
            fontSize: '11px',
          },
          formatter: (val: number) => `${val} ${cfg.unit}`,
        },
      },
      tooltip: {
        theme: 'dark' as const,
        x: {
          format: 'MMM dd, HH:mm:ss',
        },
        y: {
          formatter: (val: number) => `${val} ${cfg.unit}`,
        },
      },
      grid: {
        borderColor: dividerColor,
        strokeDashArray: 3,
      },
    };
  });

  private loadSavedFilters(): GraphsFilterState | null {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const item = window.localStorage.getItem(GRAPHS_FILTER_STORAGE_KEY);
        if (item) {
          const parsed = JSON.parse(item);
          if (parsed && typeof parsed === 'object') {
            const rawRange = parsed.timeRange ?? parsed.range ?? (parsed.days ? `${parsed.days}d` : '7d');
            const matchedOpt = findTimeRangeOption(String(rawRange));
            return {
              deviceId: typeof parsed.deviceId === 'string' ? parsed.deviceId : (typeof parsed.selectedDeviceId === 'string' ? parsed.selectedDeviceId : NODE_ALL),
              metric: typeof parsed.metric === 'string' ? parsed.metric : (typeof parsed.selectedMetric === 'string' ? parsed.selectedMetric : METRIC_TEMPERATURE),
              timeRange: matchedOpt ? matchedOpt.value : '7d',
              regularOnly: typeof parsed.regularOnly === 'boolean' ? parsed.regularOnly : false,
            };
          }
        }
      }
    } catch {
      // Ignore
    }
    return null;
  }

  private saveFilters(): void {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const state: GraphsFilterState = {
          deviceId: this.selectedDeviceId(),
          metric: this.selectedMetric(),
          timeRange: this.selectedRange(),
          regularOnly: this.regularOnly(),
        };
        window.localStorage.setItem(GRAPHS_FILTER_STORAGE_KEY, JSON.stringify(state));
      }
    } catch {
      // Ignore
    }
  }

  setRegularOnly(val: boolean): void {
    if (this.regularOnly() !== val) {
      this.regularOnly.set(val);
      this.liveReadings.set([]);
      this.saveFilters();
    }
  }

  selectMetric(metric: string): void {
    if (this.selectedMetric() !== metric) {
      this.selectedMetric.set(metric);
      this.liveReadings.set([]);
      this.saveFilters();
    }
  }

  onDeviceChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedDeviceId.set(select.value);
    this.liveReadings.set([]);
    this.saveFilters();
  }

  selectRange(rangeVal: string): void {
    const opt = findTimeRangeOption(rangeVal);
    const val = opt ? opt.value : rangeVal;
    if (this.selectedRange() !== val) {
      this.selectedRange.set(val);
      this.selectedDays.set(opt ? opt.days : null);
      this.liveReadings.set([]);
      this.saveFilters();
    }
  }

  selectDays(days: number | null): void {
    if (days === null) {
      this.selectRange('all');
    } else {
      const match = TIME_RANGE_OPTIONS.find((o) => o.days === days);
      if (match) {
        this.selectRange(match.value);
      } else {
        this.selectRange(`${days}d`);
      }
    }
  }

  onRangeChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectRange(select.value);
  }

  onDaysChange(event: Event): void {
    this.onRangeChange(event);
  }


  async refresh(): Promise<void> {
    await this.api.refresh([this.readingsResource, this.nodesResource, this.statusResource]);
  }
}
