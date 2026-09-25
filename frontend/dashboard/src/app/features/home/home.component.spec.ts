import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HomeComponent } from './home.component';
import { ApiService } from '../../services/api.service';
import {
  Node,
  SystemStatus,
  Reading,
  SYNC_STATUS_OK,
  SYNC_STATUS_OFFLINE,
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
      metrics: { temp: 22.4 },
      ingested_at: '2026-09-24T12:00:05Z',
    },
  ];

  let statusSignal = signal<SystemStatus | undefined>(mockStatus);
  let nodesSignal = signal<Node[]>(mockNodes);
  let readingsSignal = signal<Reading[]>(mockReadings);
  let statusErrorSignal = signal<any>(undefined);
  let mockApiService: any;

  beforeEach(async () => {
    statusSignal = signal<SystemStatus | undefined>(mockStatus);
    nodesSignal = signal<Node[]>(mockNodes);
    readingsSignal = signal<Reading[]>(mockReadings);
    statusErrorSignal = signal<any>(undefined);

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
      getReadings: vi.fn().mockReturnValue({
        value: readingsSignal,
        isLoading: signal(false),
        error: signal(undefined),
        reload: vi.fn(),
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
    expect(series[0].name).toBe('Temperature (°C)');
    expect(series[0].data.length).toBe(1);
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
    expect(component.chartSeries()[0].data.length).toBe(0);
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

  describe('lastSyncStatus computed', () => {
    it('should return SYNC_STATUS_OK when status is ok', () => {
      expect(component.lastSyncStatus()).toBe(SYNC_STATUS_OK);
    });

    it('should return SYNC_STATUS_OFFLINE when status is idle, error, offline, or null', () => {
      statusSignal.set({
        ...mockStatus,
        poller: { ...mockStatus.poller, last_result: { status: 'idle' } },
      });
      expect(component.lastSyncStatus()).toBe(SYNC_STATUS_OFFLINE);

      statusSignal.set({
        ...mockStatus,
        poller: { ...mockStatus.poller, last_result: { status: 'error' } },
      });
      expect(component.lastSyncStatus()).toBe(SYNC_STATUS_OFFLINE);

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
});
