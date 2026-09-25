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

  beforeEach(async () => {
    nodesSignal = signal<Node[]>(mockNodes);
    isLoadingSignal = signal<boolean>(false);
    nodesErrorSignal = signal<any>(undefined);

    mockApiService = {
      getNodes: vi.fn().mockReturnValue({
        value: nodesSignal,
        isLoading: isLoadingSignal,
        error: nodesErrorSignal,
        reload: vi.fn(),
      }),
      getStatus: vi.fn().mockReturnValue({
        value: signal({ uptime_s: 7200 }),
        isLoading: signal(false),
        error: signal(undefined),
        reload: vi.fn(),
      }),
      discover: vi.fn().mockResolvedValue({ discovered_count: 2, nodes: mockNodes }),
      sync: vi.fn().mockResolvedValue({ status: 'ok', total_ingested: 0 }),
      refresh: vi.fn().mockResolvedValue(undefined),
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
});
