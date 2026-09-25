import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChartComponent } from 'ng-apexcharts';
import {
  ApexAxisChartSeries,
} from 'ng-apexcharts';
import { ApiService } from '../../services/api.service';
import { Node, Reading } from '../../models/api.models';

export const METRIC_TEMPERATURE = 'temperature';
export const METRIC_HUMIDITY = 'humidity';
export const METRIC_LIGHT = 'light_pct';

export type MetricType =
  | typeof METRIC_TEMPERATURE
  | typeof METRIC_HUMIDITY
  | typeof METRIC_LIGHT;

export const NODE_ALL = 'all';

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

export const AVAILABLE_LIMITS = [50, 100, 200, 500];

import { TopToolbarComponent } from '../../shared/components/top-toolbar/top-toolbar.component';
import { getThemeColor } from '../../shared/utils/theme.utils';

@Component({
  selector: 'app-graphs',
  standalone: true,
  imports: [CommonModule, FormsModule, DecimalPipe, ChartComponent, TopToolbarComponent],
  templateUrl: './graphs.component.html',
  styleUrl: './graphs.component.scss',
})
export class GraphsComponent {
  private readonly api = inject(ApiService);

  readonly NODE_ALL = NODE_ALL;
  readonly METRIC_TEMPERATURE = METRIC_TEMPERATURE;
  readonly METRIC_HUMIDITY = METRIC_HUMIDITY;
  readonly METRIC_LIGHT = METRIC_LIGHT;
  readonly METRICS: MetricConfig[] = Object.values(METRIC_CONFIGS);
  readonly LIMITS = AVAILABLE_LIMITS;

  readonly selectedDeviceId = signal<string>(NODE_ALL);
  readonly selectedMetric = signal<MetricType>(METRIC_TEMPERATURE);
  readonly selectedLimit = signal<number>(100);

  readonly nodesResource = this.api.getNodes();
  readonly statusResource = this.api.getStatus();
  readonly nodes = computed<Node[]>(() => this.nodesResource.value() ?? []);

  readonly readingsResource = this.api.getReadings(() => {
    const devId = this.selectedDeviceId();
    const limit = this.selectedLimit();
    return {
      device_id: devId !== NODE_ALL ? devId : undefined,
      limit,
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
  readonly currentMetricConfig = computed<MetricConfig>(() => METRIC_CONFIGS[this.selectedMetric()]);

  // Extract numerical values in chronological order
  readonly parsedData = computed(() => {
    const items = [...this.readings()].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    const metric = this.selectedMetric();
    const points: { x: number; y: number; timestamp: string; device_id: string }[] = [];

    for (const r of items) {
      let val: unknown;
      if (metric === METRIC_TEMPERATURE) {
        val = r.metrics?.['temp'] ?? r.metrics?.['temperature'];
      } else if (metric === METRIC_HUMIDITY) {
        val = r.metrics?.['hum'] ?? r.metrics?.['humidity'];
      } else if (metric === METRIC_LIGHT) {
        val = r.metrics?.['light'] ?? r.metrics?.['light_pct'];
      }

      if (typeof val === 'number' && !isNaN(val)) {
        const timeMs = new Date(r.timestamp).getTime();
        if (!isNaN(timeMs)) {
          points.push({
            x: timeMs,
            y: Math.round(val * 10) / 10,
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
    const data = this.parsedData();
    const cfg = this.currentMetricConfig();

    // Deduplicate / average points that share the exact same timestamp
    const map = new Map<number, { sum: number; count: number }>();
    for (const d of data) {
      const entry = map.get(d.x);
      if (entry) {
        entry.sum += d.y;
        entry.count++;
      } else {
        map.set(d.x, { sum: d.y, count: 1 });
      }
    }

    const points: { x: number; y: number }[] = [];
    for (const [x, { sum, count }] of map.entries()) {
      points.push({ x, y: Math.round((sum / count) * 10) / 10 });
    }
    points.sort((a, b) => a.x - b.x);

    return [
      {
        name: `${cfg.label} (${cfg.unit})`,
        data: points,
      },
    ];
  });

  readonly chartOptions = computed(() => {
    const cfg = this.currentMetricConfig();
    const metricColor = getThemeColor(cfg.cssVar, cfg.color);
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
      colors: [metricColor],
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
        colors: [metricColor],
      },
      markers: {
        size: 4,
        colors: [metricColor],
        strokeColors: '#0B0D12',
        strokeWidth: 2,
        hover: {
          size: 7,
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

  selectMetric(metric: MetricType): void {
    this.selectedMetric.set(metric);
  }

  onDeviceChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedDeviceId.set(select.value);
  }

  onLimitChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedLimit.set(Number(select.value));
  }

  async refresh(): Promise<void> {
    await this.api.refresh([this.readingsResource, this.nodesResource, this.statusResource]);
  }
}
