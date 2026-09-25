import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HomeComponent } from './home.component';
import { ApiService } from '../../services/api.service';
import { CapabilitiesService } from '../../services/capabilities.service';
import { BOARD_PALETTE } from '../../shared/utils/chart.utils';
import {
  Node,
  SystemStatus,
  Reading,
  SYNC_STATUS_OK,
  SYNC_STATUS_OFFLINE,
  SYNC_STATUS_IDLE,
  SYNC_STATUS_ERROR,
} from '../../models/api.models';

describe('HomeComponent', () => {
  let fixture: ComponentFixture<HomeComponent>;
  let component: HomeComponent;

  const mockStatus: SystemStatus = {
    device_id: 'controller-01',
    device_type: 'laptop',
    status: 'online',
    uptime_s: 7200, // 2h 0m
    poller: {
      last_sync: '2026-09-24T12:00:00Z',
      last_result: { status: 'ok' },
      interval_s: 300,
    },
    database: {
      total_readings: 1250,
      total_nodes: 2,
      sync_states: [],
    },
  };

  const mockNodes: Node[] = [
    {
      device_id: 'node-01',
      ip_address: '192.168.1.10',
      capabilities: ['temp', 'humidity'],
      last_seen: new Date(Date.now() - 30 * 1000).toISOString(), // Online
    },
    {
      device_id: 'node-02',
      ip_address: '192.168.1.11',
      capabilities: ['light'],
      last_seen: new Date(Date.now() - 3600 * 1000).toISOString(), // Offline
    },
  ];

  const mockReadings: Reading[] = [
    {
      id: 1,
      timestamp: '2026-09-24T12:00:00Z',
      device_id: 'node-01',
      metrics: { temp: 22.4, hum: 45.0 },
      ingested_at: '2026-09-24T12:00:05Z',
    },
  ];

  let statusSignal = signal<SystemStatus | undefined>(mockStatus);
  let nodesSignal = signal<Node[]>(mockNodes);
  let readingsSignal = signal<Reading[]>(mockReadings);
  let statusErrorSignal = signal<any>(undefined);
  let mockApiService: any;
  let getReadingsParamsFn: (() => { limit?: number } | undefined) | undefined;

  beforeEach(async () => {
    statusSignal = signal<SystemStatus | undefined>(mockStatus);
    nodesSignal = signal<Node[]>(mockNodes);
    readingsSignal = signal<Reading[]>(mockReadings);
    statusErrorSignal = signal<any>(undefined);
    getReadingsParamsFn = undefined;

    mockApiService = {
      getStatus: vi.fn().mockReturnValue({
        value: statusSignal,
        isLoading: signal(false),
        error: statusErrorSignal,
        reload: vi.fn(),
      }),
      getNodes: vi.fn().mockReturnValue({
        value: nodesSignal,
        isLoading: signal(false),
        error: signal(undefined),
        reload: vi.fn(),
      }),
      getReadings: vi.fn().mockImplementation((paramsFn) => {
        getReadingsParamsFn = paramsFn;
        return {
          value: readingsSignal,
          isLoading: signal(false),
          error: signal(undefined),
          reload: vi.fn(),
        };
      }),
      discover: vi.fn().mockResolvedValue({ discovered_count: 2, nodes: mockNodes }),
      sync: vi.fn().mockResolvedValue({ status: 'ok', total_ingested: 0 }),
      refresh: vi.fn().mockResolvedValue(undefined),
      lastRefreshTimestamp: signal(Date.now()),
    };

    await TestBed.configureTestingModule({
      imports: [HomeComponent],
      providers: [
        provideRouter([]),
        { provide: ApiService, useValue: mockApiService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HomeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display summary metric cards with accurate values', () => {
    const onlineNodesEl = fixture.nativeElement.querySelector('[data-testid="metric-online-nodes"]');
    const totalRecordsEl = fixture.nativeElement.querySelector('[data-testid="metric-total-records"]');
    const syncStatusEl = fixture.nativeElement.querySelector('[data-testid="metric-sync-status"]');
    const syncIntervalEl = fixture.nativeElement.querySelector('[data-testid="metric-sync-interval"]');
    const countdownEl = fixture.nativeElement.querySelector('[data-testid="next-sync-countdown"]');

    expect(onlineNodesEl.textContent).toContain('1');
    expect(onlineNodesEl.textContent).toContain('/ 2');
    expect(totalRecordsEl.textContent).toContain('1,250');
    expect(syncStatusEl.textContent).toContain('OK');
    expect(syncIntervalEl.textContent).toContain('5m');
    expect(countdownEl.textContent).toContain('Next refresh in');
  });

  it('should calculate uptime formatting correctly', () => {
    expect(component.uptimeFormatted()).toBe('2h 0m');
  });

  it('should populate chartSeries with reading data', () => {
    const series = component.chartSeries();
    expect(series.length).toBe(1);
    expect(series[0].name).toBe('node-01');
    expect(series[0].color).toBe(BOARD_PALETTE[0]);
    expect(series[0].data.length).toBe(1);
  });

  it('should render multi-series for multiple boards with distinct cyclic colors', () => {
    readingsSignal.set([
      {
        id: 1,
        timestamp: '2026-09-24T12:00:00Z',
        device_id: 'pico-1w-01',
        metrics: { temperature: 21.5 },
        ingested_at: '2026-09-24T12:00:05Z',
      },
      {
        id: 2,
        timestamp: '2026-09-24T12:00:00Z',
        device_id: 'pico-2w-01',
        metrics: { temp: 22.0 },
        ingested_at: '2026-09-24T12:00:05Z',
      },
    ]);
    fixture.detectChanges();

    const series = component.chartSeries();
    expect(series.length).toBe(2);
    expect(series[0].name).toBe('pico-1w-01');
    expect(series[0].color).toBe(BOARD_PALETTE[0]);
    expect(series[1].name).toBe('pico-2w-01');
    expect(series[1].color).toBe(BOARD_PALETTE[1]);
  });

  it('should configure ApexCharts legend at bottom on home chart', () => {
    const options = component.chartOptions();
    expect(options.legend?.position).toBe('bottom');
    expect(options.legend?.show).toBe(true);
  });

  it('should display error message when a resource reports an error', () => {
    expect(component.hasError()).toBe(false);

    statusErrorSignal.set({ message: 'Network connection lost' });
    fixture.detectChanges();

    expect(component.hasError()).toBe(true);
    expect(component.errorMessage()).toBe('Network connection lost');
  });

  it('should handle empty states gracefully when no nodes or readings exist', () => {
    nodesSignal.set([]);
    readingsSignal.set([]);
    fixture.detectChanges();

    expect(component.onlineNodesCount()).toBe(0);
    expect(component.totalNodesCount()).toBe(0);
    expect(component.chartSeries().length).toBe(0);
  });

  it('should render top toolbar with title and subtitle', () => {
    const titleEl = fixture.nativeElement.querySelector('[data-testid="page-title"]');
    const subtitleEl = fixture.nativeElement.querySelector('[data-testid="page-subtitle"]');
    expect(titleEl.textContent).toContain('System Overview');
    expect(subtitleEl.textContent).toContain('IoTMesh Controller');
  });

  it('should delegate refresh to api.refresh', async () => {
    await component.refresh();
    expect(mockApiService.refresh).toHaveBeenCalled();
  });

  it('should reset and recalculate remaining time when refreshed', () => {
    const futureTime = Date.now();
    mockApiService.lastRefreshTimestamp.set(futureTime);
    fixture.detectChanges();

    expect(component.nextSyncRemainingSeconds()).toBeGreaterThanOrEqual(290);
    expect(component.nextSyncRemainingFormatted()).toContain('m');
  });

  it('should not get stuck in Due now when last_sync is old or in the past', () => {
    const twoHoursAgo = new Date(Date.now() - 7200 * 1000).toISOString();
    statusSignal.set({
      ...mockStatus,
      poller: {
        ...mockStatus.poller,
        last_sync: twoHoursAgo,
      },
    });
    mockApiService.lastRefreshTimestamp.set(Date.now() - 30 * 1000);
    fixture.detectChanges();

    expect(component.nextSyncRemainingSeconds()).toBeGreaterThanOrEqual(260);
    expect(component.nextSyncRemainingSeconds()).toBeLessThanOrEqual(280);
    expect(component.nextSyncRemainingFormatted()).not.toBe('Due now');
  });

  it('should trigger reloadAll and reset refresh timestamp on auto-refresh', () => {
    const reloadSpy = vi.spyOn(component, 'reloadAll');
    const pastTime = Date.now() - 305 * 1000;
    mockApiService.lastRefreshTimestamp.set(pastTime);

    (component as any).checkAutoRefresh(Date.now());

    expect(reloadSpy).toHaveBeenCalled();
    expect(mockApiService.lastRefreshTimestamp()).toBeGreaterThan(pastTime);
  });

  describe('lastSyncStatus computed', () => {
    it('should return SYNC_STATUS_OK when status is ok', () => {
      expect(component.lastSyncStatus()).toBe(SYNC_STATUS_OK);
    });

    it('should return appropriate status when status is idle, error, offline, or null', () => {
      statusSignal.set({
        ...mockStatus,
        poller: { ...mockStatus.poller, last_result: { status: 'idle' } },
      });
      expect(component.lastSyncStatus()).toBe(SYNC_STATUS_IDLE);

      statusSignal.set({
        ...mockStatus,
        poller: { ...mockStatus.poller, last_result: { status: 'error' } },
      });
      expect(component.lastSyncStatus()).toBe(SYNC_STATUS_ERROR);

      statusSignal.set({
        ...mockStatus,
        poller: { ...mockStatus.poller, last_result: { status: 'offline' } },
      });
      expect(component.lastSyncStatus()).toBe(SYNC_STATUS_OFFLINE);

      statusSignal.set({
        ...mockStatus,
        poller: { ...mockStatus.poller, last_result: null },
      });
      expect(component.lastSyncStatus()).toBe(SYNC_STATUS_OFFLINE);
    });
  });

  it('should render dynamic metric pills and switch metrics', () => {
    const capsService = TestBed.inject(CapabilitiesService);
    capsService.setCapabilities([
      { key: 'temperature', unit: 'Cel' },
      { key: 'humidity', unit: '%RH' },
    ]);
    fixture.detectChanges();

    expect(component.metrics().length).toBe(2);
    expect(component.selectedMetric()).toBe('temperature');

    component.selectMetric('humidity');
    fixture.detectChanges();

    expect(component.selectedMetric()).toBe('humidity');
    expect(component.currentMetricConfig().unit).toBe('%');
    expect(component.chartSeries()[0].name).toBe('node-01');
    const firstPoint = component.chartSeries()[0].data[0] as { x: number; y: number };
    expect(firstPoint.y).toBe(45);
  });

  it('should initialize with count options and default to 50 readings limit', () => {
    expect(component.countOptions.map((o) => o.label)).toEqual(['10', '50', '100', '200', 'All']);
    expect(component.selectedCount()).toBe(50);
    expect(getReadingsParamsFn?.()).toEqual({ limit: 50 });
  });

  it('should update selectedMetric and re-render chart without resetting selectedCount (Task 7.1)', () => {
    const capsService = TestBed.inject(CapabilitiesService);
    capsService.setCapabilities([
      { key: 'temperature', unit: 'Cel' },
      { key: 'humidity', unit: '%RH' },
    ]);
    fixture.detectChanges();

    // Change count to 100
    component.selectCount(100);
    expect(component.selectedCount()).toBe(100);
    expect(getReadingsParamsFn?.()).toEqual({ limit: 100 });

    // Switch metric to humidity
    component.selectMetric('humidity');
    fixture.detectChanges();

    // Verify metric changed and chart re-rendered with humidity value
    expect(component.selectedMetric()).toBe('humidity');
    const point = component.chartSeries()[0].data[0] as { x: number; y: number };
    expect(point.y).toBe(45.0);

    // Verify count was not reset
    expect(component.selectedCount()).toBe(100);
    expect(getReadingsParamsFn?.()).toEqual({ limit: 100 });
  });

  it('should update selectedCount and re-render without resetting selectedMetric, and All omits limit (Task 7.2)', () => {
    component.selectMetric('humidity');
    expect(component.selectedMetric()).toBe('humidity');

    // Select 10
    component.selectCount(10);
    expect(component.selectedCount()).toBe(10);
    expect(getReadingsParamsFn?.()).toEqual({ limit: 10 });
    expect(component.selectedMetric()).toBe('humidity');

    // Select 200
    component.selectCount(200);
    expect(component.selectedCount()).toBe(200);
    expect(getReadingsParamsFn?.()).toEqual({ limit: 200 });
    expect(component.selectedMetric()).toBe('humidity');

    // Select All (null) -> All omits limit param
    component.selectCount(null);
    expect(component.selectedCount()).toBeNull();
    expect(getReadingsParamsFn?.()).toBeUndefined();
    expect(component.selectedMetric()).toBe('humidity');
  });

  it('should render count selector pills in template and respond to clicks', () => {
    const countSelectorEl = fixture.nativeElement.querySelector('[data-testid="count-selector"]');
    expect(countSelectorEl).toBeTruthy();

    const pill10 = fixture.nativeElement.querySelector('[data-testid="count-pill-10"]');
    expect(pill10).toBeTruthy();
    pill10.click();
    fixture.detectChanges();

    expect(component.selectedCount()).toBe(10);
    expect(getReadingsParamsFn?.()).toEqual({ limit: 10 });

    const pillAll = fixture.nativeElement.querySelector('[data-testid="count-pill-All"]');
    expect(pillAll).toBeTruthy();
    pillAll.click();
    fixture.detectChanges();

    expect(component.selectedCount()).toBeNull();
    expect(getReadingsParamsFn?.()).toBeUndefined();
  });
});
