import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { ApiService, API_BASE_URL } from './api.service';
import { Node, SystemStatus, Reading, ReadingsQueryParams, SensorCapability } from '../models/api.models';

describe('ApiService with @Service and httpResource', () => {
  let service: ApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: '/api' },
      ],
    });
    service = TestBed.inject(ApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    TestBed.resetTestingModule();
  });

  it('should be created and auto-provided via @Service', () => {
    expect(service).toBeTruthy();
  });

  describe('getCapabilities', () => {
    it('should create an HttpResourceRef and resolve capabilities', async () => {
      const mockCapabilities: SensorCapability[] = [
        { key: 'temperature', unit: 'Cel' },
        { key: 'humidity', unit: '%RH' },
      ];

      const capsResource = TestBed.runInInjectionContext(() => service.getCapabilities());
      expect(capsResource.value()).toEqual([]);
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/capabilities');
      expect(req.request.method).toBe('GET');
      req.flush(mockCapabilities);

      await vi.waitFor(() => {
        expect(capsResource.value()).toEqual(mockCapabilities);
        expect(capsResource.isLoading()).toBe(false);
      });
    });
  });

  describe('getNodes', () => {
    it('should create an HttpResourceRef and resolve nodes', async () => {
      const mockNodes: Node[] = [
        {
          device_id: 'node-01',
          ip_address: '192.168.1.10',
          capabilities: ['temp', 'humidity'],
          last_seen: '2026-09-24T10:00:00Z',
        },
      ];

      const nodesResource = TestBed.runInInjectionContext(() => service.getNodes());
      expect(nodesResource.value()).toEqual([]);
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/nodes');
      expect(req.request.method).toBe('GET');
      req.flush(mockNodes);

      await vi.waitFor(() => {
        expect(nodesResource.value()).toEqual(mockNodes);
        expect(nodesResource.isLoading()).toBe(false);
      });
    });
  });

  describe('getStatus', () => {
    it('should create an HttpResourceRef and resolve system status', async () => {
      const mockStatus: SystemStatus = {
        device_id: 'controller-01',
        device_type: 'laptop',
        status: 'online',
        uptime_s: 500,
        poller: {
          last_sync: '2026-09-24T10:00:00Z',
          last_result: { status: 'ok' },
          interval_s: 300,
        },
        database: {
          total_readings: 100,
          total_nodes: 2,
          sync_states: [],
        },
      };

      const statusResource = TestBed.runInInjectionContext(() => service.getStatus());
      expect(statusResource.value()).toBeUndefined();
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/status');
      expect(req.request.method).toBe('GET');
      req.flush(mockStatus);

      await vi.waitFor(() => {
        expect(statusResource.value()).toEqual(mockStatus);
        expect(statusResource.isLoading()).toBe(false);
      });
    });

    it('should eliminate duplicate /api/status calls on page load by sharing the resource', async () => {
      const mockStatus: SystemStatus = {
        device_id: 'controller-01',
        device_type: 'laptop',
        status: 'online',
        uptime_s: 500,
        poller: {
          last_sync: '2026-09-24T10:00:00Z',
          last_result: { status: 'ok' },
          interval_s: 300,
        },
        database: {
          total_readings: 100,
          total_nodes: 2,
          sync_states: [],
        },
      };

      const res1 = TestBed.runInInjectionContext(() => service.getStatus());
      const res2 = TestBed.runInInjectionContext(() => service.getStatus());
      expect(res1).toBe(res2);
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/status');
      req.flush(mockStatus);

      await vi.waitFor(() => {
        expect(res1.value()).toEqual(mockStatus);
        expect(res2.value()).toEqual(mockStatus);
      });
    });

    it('should cache system status and expose systemStatus computed that survives across navigation', async () => {
      const mockStatus: SystemStatus = {
        device_id: 'controller-01',
        device_type: 'laptop',
        status: 'online',
        uptime_s: 500,
        poller: {
          last_sync: '2026-09-24T10:00:00Z',
          last_result: { status: 'ok' },
          interval_s: 300,
        },
        database: {
          total_readings: 100,
          total_nodes: 2,
          sync_states: [],
        },
      };

      TestBed.runInInjectionContext(() => service.getStatus());
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/status');
      req.flush(mockStatus);

      await vi.waitFor(() => {
        expect(service.systemStatus()).toEqual(mockStatus);
        expect(service.cachedStatus()).toEqual(mockStatus);
      });
    });

    it('should reload status via reloadStatus and prevent duplicate calls within debounce window', async () => {
      const mockStatus: SystemStatus = {
        device_id: 'controller-01',
        device_type: 'laptop',
        status: 'online',
        uptime_s: 500,
        poller: {
          last_sync: '2026-09-24T10:00:00Z',
          last_result: { status: 'ok' },
          interval_s: 300,
        },
        database: {
          total_readings: 100,
          total_nodes: 2,
          sync_states: [],
        },
      };

      // 1. Initial fetch
      TestBed.runInInjectionContext(() => service.getStatus());
      TestBed.flushEffects();
      const req1 = httpMock.expectOne('/api/status');
      req1.flush(mockStatus);

      // 2. Call reloadStatus immediately with 1000ms debounce -> should be ignored
      service.reloadStatus(1000);
      TestBed.flushEffects();
      httpMock.expectNone('/api/status');

      // 3. Call reloadStatus with 0ms debounce (bypass debounce) -> should trigger reload
      service.reloadStatus(0);
      TestBed.flushEffects();
      const req2 = httpMock.expectOne('/api/status');
      req2.flush({ ...mockStatus, uptime_s: 510 });

      await vi.waitFor(() => {
        expect(service.systemStatus()?.uptime_s).toBe(510);
      });
    });
  });

  describe('getReadings', () => {
    it('should fetch readings with static or empty params', async () => {
      const mockReadings: Reading[] = [
        {
          id: 1,
          timestamp: '2026-09-24T10:00:00Z',
          device_id: 'node-01',
          metrics: { temp: 21.5 },
          ingested_at: '2026-09-24T10:01:00Z',
        },
      ];

      const readingsResource = TestBed.runInInjectionContext(() => service.getReadings());
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/readings');
      expect(req.request.method).toBe('GET');
      req.flush(mockReadings);

      await vi.waitFor(() => {
        expect(readingsResource.value()).toEqual(mockReadings);
      });
    });

    it('should reactively update when query param signal changes', async () => {
      const paramsSignal = signal<ReadingsQueryParams | undefined>({
        device_id: 'node-01',
        limit: 10,
      });

      TestBed.runInInjectionContext(() => {
        service.getReadings(() => paramsSignal());
      });
      TestBed.flushEffects();

      const req1 = httpMock.expectOne('/api/readings?device_id=node-01&limit=10');
      req1.flush([]);

      // Update signal
      paramsSignal.set({ device_id: 'node-02', limit: 20 });
      TestBed.flushEffects();

      const req2 = httpMock.expectOne('/api/readings?device_id=node-02&limit=20');
      req2.flush([]);
    });
  });

  describe('postDisplay', () => {
    it('should send POST request to /api/display', async () => {
      const mockResponse = { status: 'success', target: 'node-01', message: 'Hi' };
      const promise = service.postDisplay('node-01', 'Hi');

      const req = httpMock.expectOne('/api/display');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ target: 'node-01', message: 'Hi' });
      req.flush(mockResponse);

      const result = await promise;
      expect(result).toEqual(mockResponse);
    });
  });

  describe('discover and sync', () => {
    it('should send POST request to /api/discover', async () => {
      const mockResponse = { discovered_count: 1, nodes: [] };
      const promise = service.discover();

      const req = httpMock.expectOne('/api/discover');
      expect(req.request.method).toBe('POST');
      req.flush(mockResponse);

      const result = await promise;
      expect(result).toEqual(mockResponse);
    });

    it('should send POST request to /api/sync', async () => {
      const mockResponse = { status: 'ok' };
      const promise = service.sync();

      const req = httpMock.expectOne('/api/sync');
      expect(req.request.method).toBe('POST');
      req.flush(mockResponse);

      const result = await promise;
      expect(result).toEqual(mockResponse);
    });
  });

  describe('refresh', () => {
    it('should trigger sync and reload all passed resources', async () => {
      const mockResource1 = { reload: vi.fn() };
      const mockResource2 = { reload: vi.fn() };

      const refreshPromise = service.refresh([mockResource1, mockResource2]);

      const req = httpMock.expectOne('/api/sync');
      expect(req.request.method).toBe('POST');
      req.flush({ status: 'ok' });

      await refreshPromise;

      expect(mockResource1.reload).toHaveBeenCalled();
      expect(mockResource2.reload).toHaveBeenCalled();
    });

    it('should not throw if sync fails and still reload resources', async () => {
      const mockResource = { reload: vi.fn() };

      const refreshPromise = service.refresh([mockResource]);

      const req = httpMock.expectOne('/api/sync');
      req.flush('Sync failure', { status: 500, statusText: 'Server Error' });

      await refreshPromise;

      expect(mockResource.reload).toHaveBeenCalled();
    });
  });

  describe('live monitoring API', () => {
    it('should send POST request to /api/live/start with rate_ms', async () => {
      const mockResponse = {
        status: 'ok',
        rate_ms: 1000,
        broker: '192.168.1.100',
        results: [{ device_id: 'pico-01', status: 'success' }],
      };
      const promise = service.startLive(1000);

      const req = httpMock.expectOne('/api/live/start');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ rate_ms: 1000 });
      req.flush(mockResponse);

      const result = await promise;
      expect(result).toEqual(mockResponse);
    });

    it('should send POST request to /api/live/stop', async () => {
      const mockResponse = {
        status: 'ok',
        results: [{ device_id: 'pico-01', status: 'success' }],
      };
      const promise = service.stopLive();

      const req = httpMock.expectOne('/api/live/stop');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({});
      req.flush(mockResponse);

      const result = await promise;
      expect(result).toEqual(mockResponse);
    });

    it('should fetch live status via GET /api/live/status', async () => {
      const mockLiveStatus = [
        { device_id: 'pico-01', rate_ms: 1000, started_at: '2026-10-04T12:00:00Z' },
      ];
      const liveResource = TestBed.runInInjectionContext(() => service.getLiveStatus());
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/live/status');
      expect(req.request.method).toBe('GET');
      req.flush(mockLiveStatus);

      await vi.waitFor(() => {
        expect(liveResource.value()).toEqual(mockLiveStatus);
      });
    });

    it('should include is_fine_tuned in getReadings query string when set', async () => {
      const readingsResource = TestBed.runInInjectionContext(() =>
        service.getReadings(() => ({ is_fine_tuned: false }))
      );
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/readings?is_fine_tuned=false');
      expect(req.request.method).toBe('GET');
      req.flush([]);

      await vi.waitFor(() => {
        expect(readingsResource.value()).toEqual([]);
      });
    });

    it('should check and update live status via checkLiveStatus and update app state signals', async () => {
      expect(service.hasCheckedLiveStatus()).toBe(false);
      expect(service.isLiveActive()).toBe(false);
      expect(service.activeLiveRateMs()).toBeNull();

      const mockLiveStatus = [
        { device_id: 'pico-01', rate_ms: 2000, started_at: '2026-10-04T12:00:00Z' },
      ];

      const checkPromise = service.checkLiveStatus(true);
      expect(service.isCheckingLiveStatus()).toBe(true);

      const req = httpMock.expectOne('/api/live/status');
      expect(req.request.method).toBe('GET');
      req.flush(mockLiveStatus);

      const result = await checkPromise;
      expect(result).toEqual(mockLiveStatus);
      expect(service.hasCheckedLiveStatus()).toBe(true);
      expect(service.isCheckingLiveStatus()).toBe(false);
      expect(service.liveStatusItems()).toEqual(mockLiveStatus);
      expect(service.isLiveActive()).toBe(true);
      expect(service.activeLiveRateMs()).toBe(2000);
    });

    it('should persist liveResultMessage across callers and clear when set to null', () => {
      expect(service.liveResultMessage()).toBeNull();
      service.liveResultMessage.set({ type: 'success', text: 'Live streaming active.' });
      expect(service.liveResultMessage()).toEqual({ type: 'success', text: 'Live streaming active.' });
      service.liveResultMessage.set(null);
      expect(service.liveResultMessage()).toBeNull();
    });

    it('should automatically update hasCheckedLiveStatus and liveStatusItems when getLiveStatus resolves', async () => {
      const mockLiveStatus = [
        { device_id: 'pico-01', rate_ms: 1000, started_at: '2026-10-04T12:00:00Z' },
      ];
      TestBed.runInInjectionContext(() => service.getLiveStatus());
      TestBed.flushEffects();

      const req = httpMock.expectOne('/api/live/status');
      req.flush(mockLiveStatus);
      TestBed.flushEffects();

      await vi.waitFor(() => {
        expect(service.hasCheckedLiveStatus()).toBe(true);
        expect(service.isLiveActive()).toBe(true);
        expect(service.activeLiveRateMs()).toBe(1000);
      });
    });
  });
});

