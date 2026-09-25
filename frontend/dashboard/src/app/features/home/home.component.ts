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
  private readonly destroyRef = inject(DestroyRef);

  readonly STATUS_ONLINE = STATUS_ONLINE;
  readonly STATUS_OFFLINE = STATUS_OFFLINE;

  readonly SYNC_STATUS_OK = SYNC_STATUS_OK;
  readonly SYNC_STATUS_OFFLINE = SYNC_STATUS_OFFLINE;
  readonly SYNC_STATUS_IDLE = SYNC_STATUS_IDLE;
  readonly SYNC_STATUS_ERROR = SYNC_STATUS_ERROR;
  readonly SYNC_STATUS_PARTIAL = SYNC_STATUS_PARTIAL;
  readonly SYNC_STATUS_BUSY = SYNC_STATUS_BUSY;

  readonly statusResource = this.api.getStatus();
  readonly nodesResource = this.api.getNodes();
  readonly readingsResource = this.api.getReadings(() => ({ limit: 50 }));

  readonly now = signal<number>(Date.now());

  constructor() {
    const reloadTimer = setInterval(() => {
      this.statusResource.reload();
      this.nodesResource.reload();
      this.readingsResource.reload();
    }, 15000);
    const tickTimer = setInterval(() => {
      this.now.set(Date.now());
    }, 1000);
    this.destroyRef.onDestroy(() => {
      clearInterval(reloadTimer);
      clearInterval(tickTimer);
    });
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
      const s = String(res['status']).toUpperCase();
      if (s === SYNC_STATUS_IDLE || s === SYNC_STATUS_ERROR || s === SYNC_STATUS_OFFLINE) {
        return SYNC_STATUS_OFFLINE;
      }
      return s;
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
    const lastSyncStr = statusVal?.poller?.last_sync;

    let baseTimeMs: number;
    if (lastSyncStr) {
      const parsed = new Date(lastSyncStr).getTime();
      baseTimeMs = isNaN(parsed)
        ? this.api.lastRefreshTimestamp()
        : Math.max(parsed, this.api.lastRefreshTimestamp());
    } else {
      baseTimeMs = this.api.lastRefreshTimestamp();
    }

    const nextSyncMs = baseTimeMs + intervalSec * 1000;
    const remainingMs = nextSyncMs - this.now();
    return Math.max(0, Math.floor(remainingMs / 1000));
  });

  readonly nextSyncRemainingFormatted = computed<string>(() => {
    return formatRemainingTime(this.nextSyncRemainingSeconds());
  });

  readonly chartSeries = computed<ApexAxisChartSeries>(() => {
    const items = [...this.readings()].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    const map = new Map<number, { sum: number; count: number }>();
    for (const r of items) {
      const val = r.metrics?.[METRIC_TEMP] ?? r.metrics?.[METRIC_TEMPERATURE];
      if (typeof val === 'number' && !isNaN(val)) {
        const timeMs = new Date(r.timestamp).getTime();
        if (!isNaN(timeMs)) {
          const entry = map.get(timeMs);
          if (entry) {
            entry.sum += val;
            entry.count++;
          } else {
            map.set(timeMs, { sum: val, count: 1 });
          }
        }
      }
    }

    const points: { x: number; y: number }[] = [];
    for (const [x, { sum, count }] of map.entries()) {
      points.push({ x, y: Math.round((sum / count) * 10) / 10 });
    }
    points.sort((a, b) => a.x - b.x);

    return [
      {
        name: 'Temperature (°C)',
        data: points,
      },
    ];
  });

  readonly chartOptions = {
    chart: {
      type: 'area' as const,
      height: 300,
      background: 'transparent',
      toolbar: { show: false },
      zoom: { enabled: false },
      animations: { enabled: true },
    },
    colors: [getThemeColor('--accent', '#2DD4BF')],
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
      colors: [getThemeColor('--accent', '#2DD4BF')],
    },
    markers: {
      size: 4,
      colors: [getThemeColor('--accent', '#2DD4BF')],
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
          colors: getThemeColor('--text-muted', '#7B8494'),
          fontSize: '11px',
        },
        datetimeUTC: false,
        format: 'HH:mm',
      },
      axisBorder: {
        color: getThemeColor('--border', 'rgba(255, 255, 255, 0.07)'),
      },
      axisTicks: {
        color: getThemeColor('--border', 'rgba(255, 255, 255, 0.07)'),
      },
    },
    tooltip: {
      theme: 'dark' as const,
      x: {
        format: 'MMM dd, HH:mm:ss',
      },
      y: {
        formatter: (val: number) => `${val} °C`,
      },
    },
    grid: {
      borderColor: getThemeColor('--divider', 'rgba(255, 255, 255, 0.06)'),
      strokeDashArray: 3,
    },
  };

  isOnline(node: Node, thresholdSeconds: number = 600): boolean {
    if (!node.last_seen) return false;
    const lastSeen = new Date(node.last_seen).getTime();
    if (isNaN(lastSeen)) return false;
    return (Date.now() - lastSeen) / 1000 <= thresholdSeconds;
  }
}
