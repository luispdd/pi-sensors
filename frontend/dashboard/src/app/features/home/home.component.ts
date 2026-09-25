import { Component, computed, DestroyRef, inject, signal } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ChartComponent } from 'ng-apexcharts';
import {
  ApexAxisChartSeries,
  ApexChart,
  ApexXAxis,
  ApexStroke,
  ApexDataLabels,
  ApexTooltip,
  ApexGrid,
  ApexMarkers,
  ApexFill,
} from 'ng-apexcharts';
import { ApiService } from '../../services/api.service';
import {
  BOARD_PALETTE,
  groupByDevice,
} from '../../shared/utils/chart.utils';
import {
  Node,
  Reading,
  SYNC_STATUS_OK,
  SYNC_STATUS_OFFLINE,
  SYNC_STATUS_IDLE,
  SYNC_STATUS_ERROR,
  SYNC_STATUS_PARTIAL,
  SYNC_STATUS_BUSY,
  SYNC_TIME_NEVER,
  METRIC_TEMPERATURE,
  METRIC_TEMP,
} from '../../models/api.models';
import {
  StatusPillComponent,
  STATUS_ONLINE,
  STATUS_OFFLINE,
} from '../../shared/components/status-pill/status-pill.component';

import { TopToolbarComponent } from '../../shared/components/top-toolbar/top-toolbar.component';
import { computedUptime, formatRemainingTime } from '../../shared/utils/formatters';
import { getThemeColor } from '../../shared/utils/theme.utils';
import { CapabilitiesService, MetricOption } from '../../services/capabilities.service';

export interface CountOption {
  label: string;
  value: number | null;
}

export const HOME_COUNT_OPTIONS: readonly CountOption[] = [
  { label: '10', value: 10 },
  { label: '50', value: 50 },
  { label: '100', value: 100 },
  { label: '200', value: 200 },
  { label: 'All', value: null },
] as const;

export interface DashboardChartOptions {
  series: ApexAxisChartSeries;
  chart: ApexChart;
  xaxis: ApexXAxis;
  stroke: ApexStroke;
  colors: string[];
  markers: ApexMarkers;
  fill: ApexFill;
  dataLabels: ApexDataLabels;
  tooltip: ApexTooltip;
  grid: ApexGrid;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    CommonModule,
    DecimalPipe,
    RouterModule,
    ChartComponent,
    StatusPillComponent,
    TopToolbarComponent,
  ],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
  })
export class HomeComponent {
  private readonly api = inject(ApiService);
  private readonly capabilitiesService = inject(CapabilitiesService);
  private readonly destroyRef = inject(DestroyRef);

  readonly STATUS_ONLINE = STATUS_ONLINE;
  readonly STATUS_OFFLINE = STATUS_OFFLINE;

  readonly SYNC_STATUS_OK = SYNC_STATUS_OK;
  readonly SYNC_STATUS_OFFLINE = SYNC_STATUS_OFFLINE;
  readonly SYNC_STATUS_IDLE = SYNC_STATUS_IDLE;
  readonly SYNC_STATUS_ERROR = SYNC_STATUS_ERROR;
  readonly SYNC_STATUS_PARTIAL = SYNC_STATUS_PARTIAL;
  readonly SYNC_STATUS_BUSY = SYNC_STATUS_BUSY;

  readonly metrics = this.capabilitiesService.metrics;
  readonly selectedMetric = signal<string>(METRIC_TEMPERATURE);

  readonly currentMetricConfig = computed<MetricOption>(() =>
    this.capabilitiesService.getMetricConfig(this.selectedMetric())
  );

  selectMetric(metric: string): void {
    this.selectedMetric.set(metric);
  }

  readonly countOptions = HOME_COUNT_OPTIONS;
  readonly selectedCount = signal<number | null>(50);

  selectCount(count: number | null): void {
    this.selectedCount.set(count);
  }

  readonly statusResource = this.api.getStatus();
  readonly nodesResource = this.api.getNodes();
  readonly readingsResource = this.api.getReadings(() => {
    const limit = this.selectedCount();
    return limit !== null ? { limit } : undefined;
  });

  readonly now = signal<number>(Date.now());
  private isAutoRefreshing = false;

  constructor() {
    const tickTimer = setInterval(() => {
      const currentTime = Date.now();
      this.now.set(currentTime);
      this.checkAutoRefresh(currentTime);
    }, 1000);
    this.destroyRef.onDestroy(() => {
      clearInterval(tickTimer);
    });
  }

  private checkAutoRefresh(currentTime: number): void {
    const statusVal = this.status();
    const intervalSec = statusVal?.poller?.interval_s ?? 300;
    const intervalMs = intervalSec * 1000;
    const lastSyncStr = statusVal?.poller?.last_sync;
    const lastRefresh = this.api.lastRefreshTimestamp();

    let baseTimeMs = lastRefresh;
    if (lastSyncStr) {
      const parsed = new Date(lastSyncStr).getTime();
      if (!isNaN(parsed) && parsed > lastRefresh && currentTime - parsed < intervalMs) {
        baseTimeMs = parsed;
      }
    }

    if (currentTime - baseTimeMs >= intervalMs && !this.isAutoRefreshing) {
      this.triggerAutoRefresh();
    }
  }

  private triggerAutoRefresh(): void {
    this.isAutoRefreshing = true;
    try {
      this.reloadAll();
    } finally {
      this.isAutoRefreshing = false;
    }
  }

  readonly status = computed(() => this.statusResource.value());
  readonly nodes = computed<Node[]>(() => this.nodesResource.value() ?? []);
  readonly readings = computed<Reading[]>(() => this.readingsResource.value() ?? []);

  readonly hasError = computed(
    () => !!(this.statusResource.error?.() || this.nodesResource.error?.() || this.readingsResource.error?.())
  );
  readonly errorMessage = computed(() => {
    const err = this.statusResource.error?.() || this.nodesResource.error?.() || this.readingsResource.error?.();
    if (!err) return null;
    return typeof err === 'object' && err !== null && 'message' in err
      ? String((err as { message: unknown }).message)
      : 'Failed to communicate with controller backend. Please verify the backend service is running.';
  });

  readonly isLoading = computed<boolean>(
    () =>
      this.statusResource.isLoading() ||
      this.nodesResource.isLoading() ||
      this.readingsResource.isLoading()
  );

  async refresh(): Promise<void> {
    await this.api.refresh([this.statusResource, this.nodesResource, this.readingsResource]);
  }

  reloadAll(): void {
    this.api.lastRefreshTimestamp.set(Date.now());
    this.statusResource.reload();
    this.nodesResource.reload();
    this.readingsResource.reload();
  }

  readonly totalRecords = computed(() => this.status()?.database?.total_readings ?? 0);
  readonly totalNodesCount = computed(() => this.nodes().length);
  readonly onlineNodesCount = computed(() => this.nodes().filter((n) => this.isOnline(n)).length);
  readonly topNodes = computed(() => this.nodes().slice(0, 5));

  readonly lastSyncStatus = computed(() => {
    const res = this.status()?.poller?.last_result;
    if (!res) return SYNC_STATUS_OFFLINE;
    if (typeof res === 'object' && 'status' in res) {
      return String(res['status']).toUpperCase();
    }
    return SYNC_STATUS_OFFLINE;
  });

  readonly lastSyncTime = computed(() => this.status()?.poller?.last_sync ?? null);

  readonly lastSyncTimeFormatted = computed(() => {
    const timeStr = this.lastSyncTime();
    if (!timeStr) return SYNC_TIME_NEVER;
    const date = new Date(timeStr);
    if (isNaN(date.getTime())) return timeStr;
    const isToday = new Date().toDateString() === date.toDateString();
    return isToday
      ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : date.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
      ' ' +
      date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  });

  readonly uptimeFormatted = computedUptime(() => this.status()?.uptime_s);

  readonly syncIntervalFormatted = computed<string>(() => {
    const sec = this.status()?.poller?.interval_s;
    if (typeof sec !== 'number' || sec <= 0) return '—';
    if (sec % 60 === 0) {
      return `${sec / 60}m`;
    }
    const mins = Math.floor(sec / 60);
    const remSec = sec % 60;
    return mins > 0 ? `${mins}m ${remSec}s` : `${sec}s`;
  });

  readonly nextSyncRemainingSeconds = computed<number>(() => {
    const statusVal = this.status();
    const intervalSec = statusVal?.poller?.interval_s ?? 300;
    const intervalMs = intervalSec * 1000;
    const lastSyncStr = statusVal?.poller?.last_sync;
    const lastRefresh = this.api.lastRefreshTimestamp();
    const now = this.now();

    let baseTimeMs = lastRefresh;
    if (lastSyncStr) {
      const parsed = new Date(lastSyncStr).getTime();
      if (!isNaN(parsed) && parsed > lastRefresh && now - parsed < intervalMs) {
        baseTimeMs = parsed;
      }
    }

    const nextSyncMs = baseTimeMs + intervalSec * 1000;
    const remainingMs = nextSyncMs - now;
    return Math.max(0, Math.floor(remainingMs / 1000));
  });

  readonly nextSyncRemainingFormatted = computed<string>(() => {
    return formatRemainingTime(this.nextSyncRemainingSeconds());
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
    const colors = this.seriesColors();
    const cfg = this.currentMetricConfig();
    const textMutedColor = getThemeColor('--text-muted', '#7B8494');
    const borderColor = getThemeColor('--border', 'rgba(255, 255, 255, 0.07)');
    const dividerColor = getThemeColor('--divider', 'rgba(255, 255, 255, 0.06)');

    return {
      chart: {
        type: 'area' as const,
        height: 300,
        background: 'transparent',
        toolbar: { show: false },
        zoom: { enabled: false },
        animations: { enabled: true },
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
        width: 2.5,
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

  isOnline(node: Node, thresholdSeconds: number = 600): boolean {
    if (!node.last_seen) return false;
    const lastSeen = new Date(node.last_seen).getTime();
    if (isNaN(lastSeen)) return false;
    return (Date.now() - lastSeen) / 1000 <= thresholdSeconds;
  }
}
