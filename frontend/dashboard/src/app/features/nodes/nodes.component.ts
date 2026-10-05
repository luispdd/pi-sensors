import { Component, computed, DestroyRef, inject, signal } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatSortModule } from '@angular/material/sort';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ApiService } from '../../services/api.service';
import { Node, LiveStatusItem } from '../../models/api.models';
import {
  StatusPillComponent,
  STATUS_ONLINE,
  STATUS_OFFLINE,
} from '../../shared/components/status-pill/status-pill.component';
import { MessageDialogComponent } from './message-dialog/message-dialog.component';
import { TopToolbarComponent } from '../../shared/components/top-toolbar/top-toolbar.component';
import { LiveControlsComponent } from '../../shared/components/live-controls/live-controls.component';

import { WebSocketService } from '../../services/websocket.service';

@Component({
  selector: 'app-nodes',
  standalone: true,
  imports: [
    CommonModule,
    DatePipe,
    MatTableModule,
    MatSortModule,
    MatDialogModule,
    StatusPillComponent,
    TopToolbarComponent,
    LiveControlsComponent,
  ],
  templateUrl: './nodes.component.html',
  styleUrl: './nodes.component.scss',
})
export class NodesComponent {
  private readonly api = inject(ApiService);
  private readonly dialog = inject(MatDialog, { optional: true });
  private readonly destroyRef = inject(DestroyRef);
  private readonly wsService = inject(WebSocketService, { optional: true });

  readonly STATUS_ONLINE = STATUS_ONLINE;
  readonly STATUS_OFFLINE = STATUS_OFFLINE;

  readonly displayedColumns: string[] = [
    'device_id',
    'status',
    'live',
    'ip_address',
    'capabilities',
    'last_seen',
    'actions',
  ];

  readonly nodesResource = this.api.getNodes();
  readonly statusResource = this.api.getStatus();
  readonly liveStatusResource = this.api.getLiveStatus();

  readonly isCheckingLive = computed<boolean>(() => {
    if (this.api.hasCheckedLiveStatus && !this.api.hasCheckedLiveStatus()) return true;
    return (this.api.isCheckingLiveStatus?.() ?? false) && !this.isLive();
  });
  readonly isLive = computed<boolean>(() => {
    if (this.api.isLiveActive?.()) return true;
    return (this.liveStatusResource.value() ?? []).length > 0;
  });
  readonly activeRateMs = computed<number>(() => {
    const rate = this.api.activeLiveRateMs?.();
    if (rate) return rate;
    const list = this.liveStatusResource.value() ?? [];
    if (list.length > 0 && list[0].rate_ms > 0) {
      return list[0].rate_ms;
    }
    return 5000;
  });

  lastRefreshTime = Date.now();
  lastStatusRefreshTime = Date.now();

  readonly nodesLastSeen = signal<Record<string, string>>({});

  constructor() {
    this.api.reloadStatus?.();

    const timer = setInterval(() => {
      this.checkCadenceRefresh();
    }, 1000);
    this.destroyRef.onDestroy(() => clearInterval(timer));

    if (this.wsService) {
      const sub = this.wsService.readings$.subscribe((reading) => {
        if (reading && reading.device_id && reading.timestamp) {
          this.nodesLastSeen.update((prev) => ({
            ...prev,
            [reading.device_id]: reading.timestamp,
          }));
        }
      });
      this.destroyRef.onDestroy(() => sub.unsubscribe());
    }
  }

  checkCadenceRefresh(now: number = Date.now()): void {
    const live = this.isLive();
    const statusVal = this.statusResource.value() ?? this.api.cachedStatus?.();
    const syncIntervalMs = (statusVal?.poller?.interval_s ?? 300) * 1000;

    // Perform /api/status request on every Sync Interval refresh
    if (now - this.lastStatusRefreshTime >= syncIntervalMs) {
      this.lastStatusRefreshTime = now;
      this.statusResource.reload();
    }

    const intervalMs = live ? this.activeRateMs() : syncIntervalMs;
    if (now - this.lastRefreshTime >= intervalMs) {
      this.lastRefreshTime = now;
      this.nodesResource.reload();
      this.liveStatusResource.reload();
      if (!live) {
        this.statusResource.reload();
        this.lastStatusRefreshTime = now;
      }
    }
  }
  readonly allNodes = computed<Node[]>(() => {
    const raw = this.nodesResource.value() ?? [];
    const overrides = this.nodesLastSeen();
    return raw.map((node) => {
      const liveSeen = overrides[node.device_id];
      if (liveSeen && liveSeen !== node.last_seen) {
        return { ...node, last_seen: liveSeen };
      }
      return node;
    });
  });

  readonly isLoading = computed<boolean>(
    () => this.nodesResource.isLoading() || this.statusResource.isLoading()
  );
  readonly hasError = computed(() => !!(this.nodesResource.error?.() || this.statusResource.error?.()));
  readonly errorMessage = computed(() => {
    const err = this.nodesResource.error?.() || this.statusResource.error?.();
    if (!err) return null;
    return typeof err === 'object' && err !== null && 'message' in err
      ? String((err as { message: unknown }).message)
      : 'Failed to load nodes from controller. Please verify the backend service is running.';
  });
  readonly filterQuery = signal<string>('');

  readonly filteredNodes = computed<Node[]>(() => {
    const query = this.filterQuery().trim().toLowerCase();
    const list = this.allNodes();
    if (!query) {
      return list;
    }
    return list.filter((node) => {
      const idMatch = node.device_id.toLowerCase().includes(query);
      const ipMatch = node.ip_address.toLowerCase().includes(query);
      const capMatch = node.capabilities.some((c) => c.toLowerCase().includes(query));
      return idMatch || ipMatch || capMatch;
    });
  });

  onSearchInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.filterQuery.set(input.value);
  }

  isOnline(node: Node, thresholdSeconds: number = 600): boolean {
    if (!node.last_seen) return false;
    const lastSeenTime = new Date(node.last_seen).getTime();
    if (isNaN(lastSeenTime)) return false;
    const now = Date.now();
    return (now - lastSeenTime) / 1000 <= thresholdSeconds;
  }

  hasDisplay(node: Node): boolean {
    return Array.isArray(node.capabilities) && node.capabilities.includes('display');
  }

  readonly liveMap = computed(() => {
    const serviceItems = this.api.liveStatusItems?.() ?? [];
    const list = serviceItems.length > 0 ? serviceItems : (this.liveStatusResource.value() ?? []);
    const map = new Map<string, LiveStatusItem>();
    for (const item of list) {
      map.set(item.device_id, item);
    }
    return map;
  });

  getLiveStatus(node: Node): LiveStatusItem | undefined {
    return this.liveMap().get(node.device_id);
  }

  onLiveChanged(): void {
    this.lastRefreshTime = Date.now();
    this.liveStatusResource.reload();
    this.nodesResource.reload();
  }

  async refresh(): Promise<void> {
    this.lastRefreshTime = Date.now();
    await this.api.refresh([this.nodesResource, this.statusResource, this.liveStatusResource]);
  }


  openMessageDialog(node: Node): void {
    if (this.dialog) {
      this.dialog.open(MessageDialogComponent, {
        data: { node },
        panelClass: 'custom-dialog-panel',
      });
    }
  }
}
