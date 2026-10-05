import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NodesComponent } from './nodes.component';
import { ApiService } from '../../services/api.service';
import { Node } from '../../models/api.models';

import { MatDialog } from '@angular/material/dialog';
import { MessageDialogComponent } from './message-dialog/message-dialog.component';

describe('NodesComponent', () => {
  let fixture: ComponentFixture<NodesComponent>;
  let component: NodesComponent;
  let mockApiService: any;
  let mockDialog: any;

  const mockNodes: Node[] = [
    {
      device_id: 'pico-01',
      ip_address: '192.168.1.101',
      capabilities: ['temp', 'humidity', 'display'],
      last_seen: new Date(Date.now() - 30 * 1000).toISOString(), // 30s ago (Online)
    },
    {
      device_id: 'pico-02',
      ip_address: '192.168.1.102',
      capabilities: ['light'],
      last_seen: new Date(Date.now() - 3600 * 1000).toISOString(), // 1 hour ago (Offline)
    },
  ];

  let nodesSignal = signal<Node[]>(mockNodes);
  let isLoadingSignal = signal<boolean>(false);
  let nodesErrorSignal = signal<any>(undefined);

  let liveStatusSignal = signal<any[]>([
    { device_id: 'pico-01', rate_ms: 500, started_at: '2026-10-04T12:00:00Z' },
  ]);
  let liveReloadSpy = vi.fn();
  let nodesReloadSpy = vi.fn();
  let statusReloadSpy = vi.fn();

  beforeEach(async () => {
    nodesSignal = signal<Node[]>(mockNodes);
    isLoadingSignal = signal<boolean>(false);
    nodesErrorSignal = signal<any>(undefined);
    liveStatusSignal = signal<any[]>([
      { device_id: 'pico-01', rate_ms: 500, started_at: '2026-10-04T12:00:00Z' },
    ]);
    liveReloadSpy = vi.fn();
    nodesReloadSpy = vi.fn();
    statusReloadSpy = vi.fn();

    mockApiService = {
      getNodes: vi.fn().mockReturnValue({
        value: nodesSignal,
        isLoading: isLoadingSignal,
        error: nodesErrorSignal,
        reload: nodesReloadSpy,
      }),
      getStatus: vi.fn().mockReturnValue({
        value: signal({ uptime_s: 7200, poller: { interval_s: 300 } }),
        isLoading: signal(false),
        error: signal(undefined),
        reload: statusReloadSpy,
      }),
      getLiveStatus: vi.fn().mockReturnValue({
        value: liveStatusSignal,
        isLoading: signal(false),
        error: signal(undefined),
        reload: liveReloadSpy,
      }),
      startLive: vi.fn().mockResolvedValue({ status: 'ok', rate_ms: 500, broker: '127.0.0.1', results: [] }),
      stopLive: vi.fn().mockResolvedValue({ status: 'ok', results: [] }),
      discover: vi.fn().mockResolvedValue({ discovered_count: 2, nodes: mockNodes }),
      sync: vi.fn().mockResolvedValue({ status: 'ok', total_ingested: 0 }),
      refresh: vi.fn().mockResolvedValue(undefined),
      checkLiveStatus: vi.fn().mockImplementation(async () => liveStatusSignal()),
      hasCheckedLiveStatus: signal(true),
      isCheckingLiveStatus: signal(false),
      liveStatusItems: liveStatusSignal,
      isLiveActive: () => liveStatusSignal().length > 0,
      activeLiveRateMs: () => (liveStatusSignal().length > 0 ? liveStatusSignal()[0].rate_ms : null),
    };


    mockDialog = {
      open: vi.spyOn(MatDialog.prototype, 'open').mockReturnValue({} as any),
    };

    await TestBed.configureTestingModule({
      imports: [NodesComponent],
      providers: [
        { provide: ApiService, useValue: mockApiService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(NodesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render all nodes in the table', () => {
    const rows = fixture.nativeElement.querySelectorAll('[data-testid="node-row"]');
    expect(rows.length).toBe(2);
    expect(rows[0].textContent).toContain('pico-01');
    expect(rows[1].textContent).toContain('pico-02');
  });

  it('should filter nodes by device ID search input', () => {
    component.filterQuery.set('pico-01');
    fixture.detectChanges();

    const rows = fixture.nativeElement.querySelectorAll('[data-testid="node-row"]');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('pico-01');
  });

  it('should correctly determine online/offline status based on last_seen', () => {
    expect(component.isOnline(mockNodes[0])).toBe(true);
    expect(component.isOnline(mockNodes[1])).toBe(false);
  });

  it('should show Message action button only for nodes with display capability', () => {
    const rows = fixture.nativeElement.querySelectorAll('[data-testid="node-row"]');
    const firstRowBtn = rows[0].querySelector('[data-testid="message-node-btn"]');
    const secondRowBtn = rows[1].querySelector('[data-testid="message-node-btn"]');

    expect(firstRowBtn).toBeTruthy();
    expect(secondRowBtn).toBeFalsy();
  });

  it('should open MessageDialogComponent when openMessageDialog is called', () => {
    component.openMessageDialog(mockNodes[0]);
    expect(mockDialog.open).toHaveBeenCalledWith(MessageDialogComponent, {
      data: { node: mockNodes[0] },
      panelClass: 'custom-dialog-panel',
    });
  });

  it('should handle error states gracefully', () => {
    expect(component.hasError()).toBe(false);

    nodesErrorSignal.set({ message: 'Failed to contact mesh controller' });
    fixture.detectChanges();

    expect(component.hasError()).toBe(true);
    expect(component.errorMessage()).toBe('Failed to contact mesh controller');
  });

  it('should handle empty nodes list', () => {
    nodesSignal.set([]);
    fixture.detectChanges();

    expect(component.filteredNodes().length).toBe(0);
  });

  it('should render top toolbar with title and subtitle', () => {
    const titleEl = fixture.nativeElement.querySelector('[data-testid="page-title"]');
    const subtitleEl = fixture.nativeElement.querySelector('[data-testid="page-subtitle"]');
    expect(titleEl.textContent).toContain('Mesh Nodes');
    expect(subtitleEl.textContent).toContain('Discovered sensor and controller nodes');
  });

  it('should delegate refresh to api.refresh', async () => {
    await component.refresh();
    expect(mockApiService.refresh).toHaveBeenCalled();
  });

  it('should show live status indicator with rate for live node, and not live for absent node', () => {
    const rows = fixture.nativeElement.querySelectorAll('[data-testid="node-row"]');
    expect(rows.length).toBe(2);

    const firstLiveEl = rows[0].querySelector('[data-testid="node-live-status"]');
    const secondLiveEl = rows[1].querySelector('[data-testid="node-live-status"]');

    expect(firstLiveEl).toBeTruthy();
    expect(firstLiveEl.textContent).toContain('Live (500ms)');

    expect(secondLiveEl).toBeTruthy();
    expect(secondLiveEl.textContent).toContain('Not live');
  });

  it('should reload live status when onLiveChanged is called', () => {
    component.onLiveChanged();
    expect(liveReloadSpy).toHaveBeenCalled();
  });

  it('should update per-node live status indicator after start and stop', () => {
    // Initially pico-01 is live at 500ms, pico-02 is not live
    let rows = fixture.nativeElement.querySelectorAll('[data-testid="node-row"]');
    expect(rows[0].querySelector('[data-testid="node-live-status"]').textContent).toContain('Live (500ms)');
    expect(rows[1].querySelector('[data-testid="node-live-status"]').textContent).toContain('Not live');

    // Simulate Start Live: both nodes live at 1000ms (1s)
    liveStatusSignal.set([
      { device_id: 'pico-01', rate_ms: 1000, started_at: '2026-10-04T12:00:00Z' },
      { device_id: 'pico-02', rate_ms: 1000, started_at: '2026-10-04T12:00:00Z' },
    ]);
    fixture.detectChanges();

    rows = fixture.nativeElement.querySelectorAll('[data-testid="node-row"]');
    expect(rows[0].querySelector('[data-testid="node-live-status"]').textContent).toContain('Live (1s)');
    expect(rows[1].querySelector('[data-testid="node-live-status"]').textContent).toContain('Live (1s)');

    // Simulate Stop Live: empty list
    liveStatusSignal.set([]);
    fixture.detectChanges();

    rows = fixture.nativeElement.querySelectorAll('[data-testid="node-row"]');
    expect(rows[0].querySelector('[data-testid="node-live-status"]').textContent).toContain('Not live');
    expect(rows[1].querySelector('[data-testid="node-live-status"]').textContent).toContain('Not live');
  });

  it('should show Checking... status while checking live status and not prematurely mark Not live', () => {
    mockApiService.hasCheckedLiveStatus.set(false);
    fixture.detectChanges();

    const rows = fixture.nativeElement.querySelectorAll('[data-testid="node-row"]');
    expect(rows[0].querySelector('[data-testid="node-live-status"]').textContent).toContain('Checking...');
    expect(rows[1].querySelector('[data-testid="node-live-status"]').textContent).toContain('Checking...');
  });

  describe('Task 6.1 & 6.2: Polling cadence and live telemetry refresh', () => {
    it('should not reload automatically when live monitoring is inactive and less than 5 minutes have elapsed', () => {
      liveStatusSignal.set([]);
      fixture.detectChanges();

      nodesReloadSpy.mockClear();
      statusReloadSpy.mockClear();

      // Advance by 15 seconds (old excessive polling interval)
      component.checkCadenceRefresh(component.lastRefreshTime + 15000);

      expect(nodesReloadSpy).not.toHaveBeenCalled();
      expect(statusReloadSpy).not.toHaveBeenCalled();
    });

    it('should refresh automatically only after 5 minutes when live monitoring is inactive', () => {
      liveStatusSignal.set([]);
      fixture.detectChanges();

      nodesReloadSpy.mockClear();
      statusReloadSpy.mockClear();

      // Advance by 5 minutes (300,000 ms)
      component.checkCadenceRefresh(component.lastRefreshTime + 300000);

      expect(nodesReloadSpy).toHaveBeenCalled();
      expect(statusReloadSpy).toHaveBeenCalled();
    });

    it('should refresh dynamically at configured cadence (e.g. 5 seconds) when live monitoring is active', () => {
      liveStatusSignal.set([{ device_id: 'pico-01', rate_ms: 5000 }]);
      fixture.detectChanges();

      nodesReloadSpy.mockClear();

      // Advance by 2 seconds (< 5 seconds)
      component.checkCadenceRefresh(component.lastRefreshTime + 2000);
      expect(nodesReloadSpy).not.toHaveBeenCalled();

      // Advance by 5 seconds (= 5000 ms cadence)
      component.checkCadenceRefresh(component.lastRefreshTime + 5000);
      expect(nodesReloadSpy).toHaveBeenCalled();
    });
  });
});

