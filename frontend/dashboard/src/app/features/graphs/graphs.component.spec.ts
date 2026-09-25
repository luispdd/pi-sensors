import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  GraphsComponent,
  METRIC_TEMPERATURE,
  METRIC_HUMIDITY,
  METRIC_LIGHT,
  NODE_ALL,
} from './graphs.component';
import { ApiService } from '../../services/api.service';
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
  let mockApiService: any;

  beforeEach(async () => {
    nodesSignal = signal<Node[]>(mockNodes);
    readingsSignal = signal<Reading[]>(mockReadings);
    readingsErrorSignal = signal<any>(undefined);
    getReadingsSpy = vi.fn().mockImplementation((paramsFn) => ({
      value: readingsSignal,
      isLoading: signal(false),
      error: readingsErrorSignal,
      reload: vi.fn(),
    }));

    mockApiService = {
      getNodes: vi.fn().mockReturnValue({ value: nodesSignal, isLoading: signal(false), error: signal(undefined), reload: vi.fn() }),
      getStatus: vi.fn().mockReturnValue({ value: signal({ uptime_s: 7200 }), isLoading: signal(false), error: signal(undefined), reload: vi.fn() }),
      getReadings: getReadingsSpy,
      discover: vi.fn().mockResolvedValue({ discovered_count: 2, nodes: mockNodes }),
      sync: vi.fn().mockResolvedValue({ status: 'ok', total_ingested: 0 }),
      refresh: vi.fn().mockResolvedValue(undefined),
    };

    await TestBed.configureTestingModule({
      imports: [GraphsComponent],
      providers: [{ provide: ApiService, useValue: mockApiService }],
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

  it('should populate chartSeries with correct metric label and values', () => {
    const series = component.chartSeries();
    expect(series.length).toBe(1);
    expect(series[0].name).toContain('Temperature (°C)');
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
    expect(series[0].name).toContain('Humidity (%)');
  });

  it('should update series and stats when switching to light metric', () => {
    component.selectMetric(METRIC_LIGHT);
    fixture.detectChanges();
    expect(component.stats().latest).toBe(90);

    const series = component.chartSeries();
    expect(series[0].name).toContain('Light Level (%)');
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
    expect(series[0].data.length).toBe(0);
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
});
