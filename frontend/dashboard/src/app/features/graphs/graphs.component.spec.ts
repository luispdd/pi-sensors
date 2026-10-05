import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  GraphsComponent,
  METRIC_TEMPERATURE,
  METRIC_HUMIDITY,
  METRIC_LIGHT,
  NODE_ALL,
  RANGE_ALL,
  GRAPHS_FILTER_STORAGE_KEY,
} from './graphs.component';
import { Subject } from 'rxjs';
import { ApiService } from '../../services/api.service';
import { WebSocketService } from '../../services/websocket.service';
import { CapabilitiesService } from '../../services/capabilities.service';
import { BOARD_PALETTE } from '../../shared/utils/chart.utils';
import { Node, Reading } from '../../models/api.models';

describe('GraphsComponent', () => {
  let fixture: ComponentFixture<GraphsComponent>;
  let component: GraphsComponent;

  const mockNodes: Node[] = [
    {
      device_id: 'node-01',
      ip_address: '192.168.1.10',
      capabilities: ['temp', 'humidity'],
      last_seen: new Date().toISOString(),
    },
    {
      device_id: 'node-02',
      ip_address: '192.168.1.11',
      capabilities: ['light'],
      last_seen: new Date().toISOString(),
    },
  ];

  const mockReadings: Reading[] = [
    {
      id: 1,
      timestamp: '2026-09-24T12:00:00Z',
      device_id: 'node-01',
      metrics: { temp: 20.0, humidity: 45.0, light_pct: 80 },
      ingested_at: '2026-09-24T12:00:05Z',
    },
    {
      id: 2,
      timestamp: '2026-09-24T12:05:00Z',
      device_id: 'node-01',
      metrics: { temp: 24.0, humidity: 55.0, light_pct: 90 },
      ingested_at: '2026-09-24T12:05:05Z',
    },
  ];

  let nodesSignal = signal<Node[]>(mockNodes);
  let readingsSignal = signal<Reading[]>(mockReadings);
  let readingsErrorSignal = signal<any>(undefined);
  let getReadingsSpy = vi.fn();
  let lastParamsFn: (() => any) | undefined;
  let mockApiService: any;
  let wsReadingsSubject: Subject<Reading>;
  let mockWsService: any;

  beforeEach(async () => {
    localStorage.clear();
    nodesSignal = signal<Node[]>(mockNodes);
    readingsSignal = signal<Reading[]>(mockReadings);
    readingsErrorSignal = signal<any>(undefined);
    lastParamsFn = undefined;
    wsReadingsSubject = new Subject<Reading>();
    mockWsService = {
      readings$: wsReadingsSubject.asObservable(),
      status: signal('connected'),
      connect: vi.fn(),
      disconnect: vi.fn(),
    };
    getReadingsSpy = vi.fn().mockImplementation((paramsFn) => {
      lastParamsFn = paramsFn;
      return {
        value: readingsSignal,
        isLoading: signal(false),
        error: readingsErrorSignal,
        reload: vi.fn(),
      };
    });

    mockApiService = {
      getNodes: vi.fn().mockReturnValue({ value: nodesSignal, isLoading: signal(false), error: signal(undefined), reload: vi.fn() }),
      getStatus: vi.fn().mockReturnValue({ value: signal({ uptime_s: 7200 }), isLoading: signal(false), error: signal(undefined), reload: vi.fn() }),
      getReadings: getReadingsSpy,
      discover: vi.fn().mockResolvedValue({ discovered_count: 2, nodes: mockNodes }),
      sync: vi.fn().mockResolvedValue({ status: 'ok', total_ingested: 0 }),
      refresh: vi.fn().mockResolvedValue(undefined),
      getLiveStatus: vi.fn().mockReturnValue({
        value: signal([]),
        isLoading: signal(false),
        error: signal(undefined),
        reload: vi.fn(),
      }),
      checkLiveStatus: vi.fn().mockResolvedValue([]),
      hasCheckedLiveStatus: signal(true),
      isCheckingLiveStatus: signal(false),
      liveStatusItems: signal([]),
      isLiveActive: signal(false),
      activeLiveRateMs: signal(null),
      startLive: vi.fn().mockResolvedValue({ status: 'ok', results: [] }),
      stopLive: vi.fn().mockResolvedValue({ status: 'ok', results: [] }),
    };

    await TestBed.configureTestingModule({
      imports: [GraphsComponent],
      providers: [
        { provide: ApiService, useValue: mockApiService },
        { provide: WebSocketService, useValue: mockWsService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(GraphsComponent);
    component = fixture.componentInstance;

    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize with default temperature metric and all nodes selected', () => {
    expect(component.selectedMetric()).toBe(METRIC_TEMPERATURE);
    expect(component.selectedDeviceId()).toBe(NODE_ALL);
  });

  it('should compute stats correctly for temperature readings', () => {
    const stats = component.stats();
    expect(stats.min).toBe(20.0);
    expect(stats.max).toBe(24.0);
    expect(stats.avg).toBe(22.0);
    expect(stats.latest).toBe(24.0);
    expect(stats.count).toBe(2);
  });

  it('should populate chartSeries with device ID and values', () => {
    const series = component.chartSeries();
    expect(series.length).toBe(1);
    expect(series[0].name).toBe('node-01');
    expect(series[0].color).toBe(BOARD_PALETTE[0]);
    expect(series[0].data.length).toBe(2);
  });

  it('should update series and stats when switching to humidity metric', () => {
    component.selectMetric(METRIC_HUMIDITY);
    fixture.detectChanges();

    expect(component.selectedMetric()).toBe(METRIC_HUMIDITY);
    const stats = component.stats();
    expect(stats.min).toBe(45.0);
    expect(stats.max).toBe(55.0);
    expect(stats.avg).toBe(50.0);
    expect(stats.latest).toBe(55.0);

    const series = component.chartSeries();
    expect(series[0].name).toBe('node-01');
  });

  it('should update series and stats when switching to light metric', () => {
    component.selectMetric(METRIC_LIGHT);
    fixture.detectChanges();
    expect(component.stats().latest).toBe(90);

    const series = component.chartSeries();
    expect(series[0].name).toBe('node-01');
  });

  it('should produce multiple series with distinct cyclic colors for multiple boards', () => {
    readingsSignal.set([
      {
        id: 1,
        timestamp: '2026-09-24T12:00:00Z',
        device_id: 'node-01',
        metrics: { temp: 20.0 },
        ingested_at: '2026-09-24T12:00:05Z',
      },
      {
        id: 2,
        timestamp: '2026-09-24T12:00:00Z',
        device_id: 'node-02',
        metrics: { temp: 25.0 },
        ingested_at: '2026-09-24T12:00:05Z',
      },
    ]);
    fixture.detectChanges();

    const series = component.chartSeries();
    expect(series.length).toBe(2);
    expect(series[0].name).toBe('node-01');
    expect(series[0].color).toBe(BOARD_PALETTE[0]);
    expect(series[1].name).toBe('node-02');
    expect(series[1].color).toBe(BOARD_PALETTE[1]);
  });

  it('should configure ApexCharts legend at the bottom', () => {
    const options = component.chartOptions();
    expect(options.legend?.position).toBe('bottom');
    expect(options.legend?.show).toBe(true);
  });

  it('should handle empty readings gracefully', () => {
    readingsSignal.set([]);
    fixture.detectChanges();

    const stats = component.stats();
    expect(stats.count).toBe(0);
    expect(stats.min).toBeNull();
    expect(stats.max).toBeNull();
    expect(stats.avg).toBeNull();
    expect(stats.latest).toBeNull();

    const series = component.chartSeries();
    expect(series.length).toBe(0);
  });

  it('should handle error states gracefully', () => {
    expect(component.hasError()).toBe(false);

    readingsErrorSignal.set({ message: 'Telemetry service unavailable' });
    fixture.detectChanges();

    expect(component.hasError()).toBe(true);
    expect(component.errorMessage()).toBe('Telemetry service unavailable');
  });

  it('should render top toolbar with title and subtitle', () => {
    const titleEl = fixture.nativeElement.querySelector('[data-testid="page-title"]');
    const subtitleEl = fixture.nativeElement.querySelector('[data-testid="page-subtitle"]');
    expect(titleEl.textContent).toContain('Telemetry & Analytics');
    expect(subtitleEl.textContent).toContain('Interactive time-series telemetry charts');
  });

  it('should delegate refresh to api.refresh', async () => {
    await component.refresh();
    expect(mockApiService.refresh).toHaveBeenCalled();
  });

  it('should derive metric pills from dynamic capabilities with unit mapping', () => {
    const capsService = TestBed.inject(CapabilitiesService);
    capsService.setCapabilities([
      { key: 'temperature', unit: 'Cel' },
      { key: 'humidity', unit: '%RH' },
      { key: 'pressure', unit: 'hPa' },
    ]);
    fixture.detectChanges();

    const metrics = component.metrics();
    expect(metrics.length).toBe(3);
    expect(metrics[0]).toEqual(expect.objectContaining({ id: 'temperature', label: 'Temperature', unit: '°C' }));
    expect(metrics[1]).toEqual(expect.objectContaining({ id: 'humidity', label: 'Humidity', unit: '%' }));
    expect(metrics[2]).toEqual(expect.objectContaining({ id: 'pressure', label: 'Pressure', unit: 'hPa' }));

    const pillTexts = Array.from(fixture.nativeElement.querySelectorAll('button')).map((p: any) => p.textContent.trim());
    expect(pillTexts.some((t: string) => t.includes('Temperature') && t.includes('(°C)'))).toBe(true);
    expect(pillTexts.some((t: string) => t.includes('Humidity') && t.includes('(%)'))).toBe(true);
    expect(pillTexts.some((t: string) => t.includes('Pressure') && t.includes('(hPa)'))).toBe(true);
  });

  it('should initialize with day-range options and default to Last 7d', () => {
    expect(component.dayRangeOptions.map((o) => o.label)).toEqual([
      'Last 10m',
      'Last 1h',
      'Last 3h',
      'Last 6h',
      'Last 1d',
      'Last 3d',
      'Last 7d',
      'Last 14d',
      'Last 30d',
      'All',
    ]);
    expect(component.selectedDays()).toBe(7);

    const params = lastParamsFn?.();
    expect(params.since).toBeDefined();
    const sinceTime = new Date(params.since).getTime();
    const expectedTime = Date.now() - 7 * 86400000;
    expect(Math.abs(sinceTime - expectedTime)).toBeLessThan(5000);
  });

  it('should compute since for Last 10m returning past 10 minutes (Task 7.2)', () => {
    component.selectRange('10m');
    fixture.detectChanges();

    expect(component.selectedRange()).toBe('10m');
    const params = lastParamsFn?.();
    expect(params.since).toBeDefined();

    const sinceTime = new Date(params.since).getTime();
    const expected10mAgo = Date.now() - 10 * 60 * 1000;
    expect(Math.abs(sinceTime - expected10mAgo)).toBeLessThan(5000);
  });

  it('should compute since for Last 1h returning past 1 hour (Task 7.2)', () => {
    component.selectRange('1h');
    fixture.detectChanges();

    expect(component.selectedRange()).toBe('1h');
    const params = lastParamsFn?.();
    expect(params.since).toBeDefined();

    const sinceTime = new Date(params.since).getTime();
    const expected1hAgo = Date.now() - 60 * 60 * 1000;
    expect(Math.abs(sinceTime - expected1hAgo)).toBeLessThan(5000);
  });

  it('should compute since for Last 3h and Last 6h (Task 7.2)', () => {
    component.selectRange('3h');
    fixture.detectChanges();
    expect(Math.abs(new Date(lastParamsFn?.().since).getTime() - (Date.now() - 3 * 3600 * 1000))).toBeLessThan(5000);

    component.selectRange('6h');
    fixture.detectChanges();
    expect(Math.abs(new Date(lastParamsFn?.().since).getTime() - (Date.now() - 6 * 3600 * 1000))).toBeLessThan(5000);
  });

  it('should compute since for Last 1d returning past 24 hours (Task 8.2)', () => {
    component.selectDays(1);
    fixture.detectChanges();

    expect(component.selectedDays()).toBe(1);
    const params = lastParamsFn?.();
    expect(params.since).toBeDefined();

    const sinceTime = new Date(params.since).getTime();
    const expected24hAgo = Date.now() - 1 * 86400000;
    expect(Math.abs(sinceTime - expected24hAgo)).toBeLessThan(5000);
  });

  it('should omit since parameter when All is selected (Task 8.2)', () => {
    component.selectDays(null);
    fixture.detectChanges();

    expect(component.selectedDays()).toBeNull();
    const params = lastParamsFn?.();
    expect(params.since).toBeUndefined();
  });

  it('should render day-range dropdown in template and update selectedDays on change (Task 8.1)', () => {
    const selectEl: HTMLSelectElement = fixture.nativeElement.querySelector('[data-testid="range-select"]');
    expect(selectEl).toBeTruthy();

    const options = Array.from(selectEl.options).map((opt) => opt.text);
    expect(options).toEqual([
      'Last 10m',
      'Last 1h',
      'Last 3h',
      'Last 6h',
      'Last 1d',
      'Last 3d',
      'Last 7d',
      'Last 14d',
      'Last 30d',
      'All',
    ]);

    // Select 10m
    selectEl.value = '10m';
    selectEl.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(component.selectedRange()).toBe('10m');
    const params10m = lastParamsFn?.();
    expect(Math.abs(new Date(params10m.since).getTime() - (Date.now() - 10 * 60 * 1000))).toBeLessThan(5000);

    // Select 30d
    selectEl.value = '30d';
    selectEl.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(component.selectedDays()).toBe(30);
    const params = lastParamsFn?.();
    const sinceTime = new Date(params.since).getTime();
    const expected30dAgo = Date.now() - 30 * 86400000;
    expect(Math.abs(sinceTime - expected30dAgo)).toBeLessThan(5000);

    // Select All
    selectEl.value = RANGE_ALL;
    selectEl.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(component.selectedDays()).toBeNull();
    expect(lastParamsFn?.().since).toBeUndefined();
  });

  describe('Per-Board Statistics (Tasks 9.1 and 9.2)', () => {
    const multiBoardReadings: Reading[] = [
      {
        id: 1,
        timestamp: '2026-09-24T12:00:00Z',
        device_id: 'pico-01',
        metrics: { temp: 20.0 },
        ingested_at: '2026-09-24T12:00:05Z',
      },
      {
        id: 2,
        timestamp: '2026-09-24T12:05:00Z',
        device_id: 'pico-01',
        metrics: { temp: 24.0 },
        ingested_at: '2026-09-24T12:05:05Z',
      },
      {
        id: 3,
        timestamp: '2026-09-24T12:00:00Z',
        device_id: 'pico-02',
        metrics: { temp: 15.0 },
        ingested_at: '2026-09-24T12:00:05Z',
      },
      {
        id: 4,
        timestamp: '2026-09-24T12:05:00Z',
        device_id: 'pico-02',
        metrics: { temp: 25.0 },
        ingested_at: '2026-09-24T12:05:05Z',
      },
    ];

    it('should compute perBoardStats correctly for multiple boards (Task 9.1)', () => {
      readingsSignal.set(multiBoardReadings);
      fixture.detectChanges();

      const perBoard = component.perBoardStats();
      expect(perBoard.length).toBe(2);

      const board1 = perBoard.find((b) => b.device_id === 'pico-01');
      expect(board1).toBeDefined();
      expect(board1?.min).toBe(20.0);
      expect(board1?.max).toBe(24.0);
      expect(board1?.avg).toBe(22.0);
      expect(board1?.latest).toBe(24.0);
      expect(board1?.color).toBe(BOARD_PALETTE[0]);

      const board2 = perBoard.find((b) => b.device_id === 'pico-02');
      expect(board2).toBeDefined();
      expect(board2?.min).toBe(15.0);
      expect(board2?.max).toBe(25.0);
      expect(board2?.avg).toBe(20.0);
      expect(board2?.latest).toBe(25.0);
      expect(board2?.color).toBe(BOARD_PALETTE[1]);
    });

    it('should show stats table below graph when 2 or more boards are visible', () => {
      readingsSignal.set(multiBoardReadings);
      fixture.detectChanges();

      const tableEl = fixture.nativeElement.querySelector('[data-testid="per-board-stats-table"]');
      const cardsEl = fixture.nativeElement.querySelector('[data-testid="stat-cards"]');

      expect(tableEl).toBeTruthy();
      expect(cardsEl).toBeNull();

      const row1 = fixture.nativeElement.querySelector('[data-testid="board-stat-row-pico-01"]');
      const row2 = fixture.nativeElement.querySelector('[data-testid="board-stat-row-pico-02"]');
      expect(row1).toBeTruthy();
      expect(row2).toBeTruthy();
      expect(row1.textContent).toContain('pico-01');
      expect(row1.textContent).toContain('20');
      expect(row1.textContent).toContain('24');
      expect(row1.textContent).toContain('22');
      expect(row2.textContent).toContain('pico-02');
      expect(row2.textContent).toContain('15');
      expect(row2.textContent).toContain('25');
    });

    it('should show stats table below graph and no stat cards when a single board is selected', () => {
      // Filter down to single board
      readingsSignal.set([
        {
          id: 1,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'pico-01',
          metrics: { temp: 20.0 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
      ]);
      fixture.detectChanges();

      const tableEl = fixture.nativeElement.querySelector('[data-testid="per-board-stats-table"]');
      const cardsEl = fixture.nativeElement.querySelector('[data-testid="stat-cards"]');

      expect(tableEl).toBeTruthy();
      expect(cardsEl).toBeNull();
      const row = fixture.nativeElement.querySelector('[data-testid="board-stat-row-pico-01"]');
      expect(row).toBeTruthy();
      expect(row.textContent).toContain('pico-01');
      expect(row.textContent).toContain('20');
    });

    it('should hide stats table when there are no readings', () => {
      readingsSignal.set([]);
      fixture.detectChanges();

      const tableEl = fixture.nativeElement.querySelector('[data-testid="per-board-stats-table"]');
      const cardsEl = fixture.nativeElement.querySelector('[data-testid="stat-cards"]');

      expect(tableEl).toBeNull();
      expect(cardsEl).toBeNull();
    });
  });

  describe('Task 4.3: Graph Data Filter Toggle', () => {
    it('should default to all data with is_fine_tuned omitted in query params', () => {
      expect(component.regularOnly()).toBe(false);
      const params = lastParamsFn ? lastParamsFn() : undefined;
      expect(params?.is_fine_tuned).toBeUndefined();
    });

    it('should send is_fine_tuned=false when regular-only filter is selected', () => {
      const regBtn = fixture.nativeElement.querySelector('[data-testid="filter-regular-btn"]');
      regBtn.click();
      fixture.detectChanges();

      expect(component.regularOnly()).toBe(true);
      const params = lastParamsFn ? lastParamsFn() : undefined;
      expect(params?.is_fine_tuned).toBe(false);
    });

    it('should omit is_fine_tuned when toggled back to all data', () => {
      component.setRegularOnly(true);
      fixture.detectChanges();

      const allBtn = fixture.nativeElement.querySelector('[data-testid="filter-all-btn"]');
      allBtn.click();
      fixture.detectChanges();

      expect(component.regularOnly()).toBe(false);
      const params = lastParamsFn ? lastParamsFn() : undefined;
      expect(params?.is_fine_tuned).toBeUndefined();
    });
  });

  describe('Task 4.4: Live Chart Updates over WebSocket', () => {
    it('should append matching reading to chart without polling', () => {
      const initialCount = component.allReadings().length;
      expect(initialCount).toBe(2);

      const newReading: Reading = {
        device_id: 'node-01',
        timestamp: '2026-09-24T12:10:00Z',
        metrics: { temp: 26.5 },
        is_fine_tuned: true,
      };

      wsReadingsSubject.next(newReading);
      fixture.detectChanges();

      expect(component.allReadings().length).toBe(3);
      expect(component.allReadings()[2].timestamp).toBe('2026-09-24T12:10:00Z');
      expect(getReadingsSpy).toHaveBeenCalledTimes(1); // No re-polling
    });

    it('should ignore reading for non-matching device when device filter is active', () => {
      component.selectedDeviceId.set('node-01');
      fixture.detectChanges();

      const initialCount = component.allReadings().length;

      const nonMatchingReading: Reading = {
        device_id: 'node-02',
        timestamp: '2026-09-24T12:10:00Z',
        metrics: { temp: 21.0 },
      };

      wsReadingsSubject.next(nonMatchingReading);
      fixture.detectChanges();

      expect(component.allReadings().length).toBe(initialCount);
    });

    it('should ignore reading that lacks the currently displayed metric', () => {
      component.selectedMetric.set(METRIC_TEMPERATURE);
      fixture.detectChanges();

      const initialCount = component.allReadings().length;

      const nonMetricReading: Reading = {
        device_id: 'node-01',
        timestamp: '2026-09-24T12:10:00Z',
        metrics: { humidity: 55 }, // No temp / temperature
      };

      wsReadingsSubject.next(nonMetricReading);
      fixture.detectChanges();

      expect(component.allReadings().length).toBe(initialCount);
    });

    it('should not append live reading when regular-only filter is active', () => {
      component.setRegularOnly(true);
      fixture.detectChanges();

      const initialCount = component.allReadings().length;

      const liveReading: Reading = {
        device_id: 'node-01',
        timestamp: '2026-09-24T12:10:00Z',
        metrics: { temp: 28.0 },
        is_fine_tuned: true,
      };

      wsReadingsSubject.next(liveReading);
      fixture.detectChanges();

      expect(component.allReadings().length).toBe(initialCount);
    });

    it('should append regular reading (is_fine_tuned=false) when regular-only filter is active', () => {
      component.setRegularOnly(true);
      fixture.detectChanges();

      const initialCount = component.allReadings().length;

      const regularReading: Reading = {
        device_id: 'node-01',
        timestamp: '2026-09-24T12:10:00Z',
        metrics: { temp: 28.0 },
        is_fine_tuned: false,
      };

      wsReadingsSubject.next(regularReading);
      fixture.detectChanges();

      expect(component.allReadings().length).toBe(initialCount + 1);
    });

    it('should render live controls component below top toolbar (Task 7.1)', () => {
      const liveControlsEl = fixture.nativeElement.querySelector('app-live-controls');
      expect(liveControlsEl).toBeTruthy();
    });
  });

  describe('LocalStorage Filter Persistence (Task 7.3)', () => {
    it('should persist selected filters to localStorage when modified', () => {
      component.onDeviceChange({ target: { value: 'node-01' } } as unknown as Event);
      component.selectMetric(METRIC_HUMIDITY);
      component.selectRange('1h');
      component.setRegularOnly(true);

      const stored = localStorage.getItem(GRAPHS_FILTER_STORAGE_KEY);
      expect(stored).toBeTruthy();
      const parsed = JSON.parse(stored!);
      expect(parsed.deviceId).toBe('node-01');
      expect(parsed.metric).toBe(METRIC_HUMIDITY);
      expect(parsed.timeRange).toBe('1h');
      expect(parsed.regularOnly).toBe(true);
    });

    it('should restore saved filters from localStorage on initialization', () => {
      localStorage.setItem(
        GRAPHS_FILTER_STORAGE_KEY,
        JSON.stringify({
          deviceId: 'node-02',
          metric: METRIC_LIGHT,
          timeRange: '10m',
          regularOnly: true,
        })
      );

      const restoredFixture = TestBed.createComponent(GraphsComponent);
      const restoredComponent = restoredFixture.componentInstance;
      restoredFixture.detectChanges();

      expect(restoredComponent.selectedDeviceId()).toBe('node-02');
      expect(restoredComponent.selectedMetric()).toBe(METRIC_LIGHT);
      expect(restoredComponent.selectedRange()).toBe('10m');
      expect(restoredComponent.regularOnly()).toBe(true);
    });
  });
});

