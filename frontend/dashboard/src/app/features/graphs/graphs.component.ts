import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChartComponent } from 'ng-apexcharts';
import {
  ApexAxisChartSeries,
} from 'ng-apexcharts';
import { ApiService } from '../../services/api.service';
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

export interface DayRangeOption {
  label: string;
  days: number | null;
}

export const DAY_RANGE_OPTIONS: readonly DayRangeOption[] = [
  { label: 'Last 1d', days: 1 },
  { label: 'Last 3d', days: 3 },
  { label: 'Last 7d', days: 7 },
  { label: 'Last 14d', days: 14 },
  { label: 'Last 30d', days: 30 },
  { label: 'All', days: null },
] as const;

import { TopToolbarComponent } from '../../shared/components/top-toolbar/top-toolbar.component';
import { getThemeColor } from '../../shared/utils/theme.utils';
import { CapabilitiesService, MetricOption } from '../../services/capabilities.service';

@Component({
  selector: 'app-graphs',
  standalone: true,
  imports: [CommonModule, FormsModule, DecimalPipe, ChartComponent, TopToolbarComponent],
  templateUrl: './graphs.component.html',
  styleUrl: './graphs.component.scss',
})
export class GraphsComponent {
  private readonly api = inject(ApiService);
  private readonly capabilitiesService = inject(CapabilitiesService);

  readonly NODE_ALL = NODE_ALL;
  readonly RANGE_ALL = RANGE_ALL;
  readonly METRIC_TEMPERATURE = METRIC_TEMPERATURE;
  readonly METRIC_HUMIDITY = METRIC_HUMIDITY;
  readonly METRIC_LIGHT = METRIC_LIGHT;
  readonly metrics = this.capabilitiesService.metrics;
  readonly dayRangeOptions = DAY_RANGE_OPTIONS;

  readonly selectedDeviceId = signal<string>(NODE_ALL);
  readonly selectedMetric = signal<string>(METRIC_TEMPERATURE);
  readonly selectedDays = signal<number | null>(7);

  readonly nodesResource = this.api.getNodes();
  readonly statusResource = this.api.getStatus();
  readonly nodes = computed<Node[]>(() => this.nodesResource.value() ?? []);

  readonly readingsResource = this.api.getReadings(() => {
    const devId = this.selectedDeviceId();
    const days = this.selectedDays();
    const since =
      days !== null
        ? new Date(Date.now() - days * 86400000).toISOString()
        : undefined;

    return {
      device_id: devId !== NODE_ALL ? devId : undefined,
      since,
    };
  });

  readonly readings = computed<Reading[]>(() => this.readingsResource.value() ?? []);
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

  selectMetric(metric: string): void {
    this.selectedMetric.set(metric);
  }

  onDeviceChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedDeviceId.set(select.value);
  }

  selectDays(days: number | null): void {
    this.selectedDays.set(days);
  }

  onDaysChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const val = select.value;
    this.selectedDays.set(val === RANGE_ALL || val === '' ? null : Number(val));
  }

  async refresh(): Promise<void> {
    await this.api.refresh([this.readingsResource, this.nodesResource, this.statusResource]);
  }
}
