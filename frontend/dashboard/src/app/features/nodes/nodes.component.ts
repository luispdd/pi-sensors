import { Component, computed, DestroyRef, inject, signal } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatSortModule } from '@angular/material/sort';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ApiService } from '../../services/api.service';
import { Node } from '../../models/api.models';
import {
  StatusPillComponent,
  STATUS_ONLINE,
  STATUS_OFFLINE,
} from '../../shared/components/status-pill/status-pill.component';
import { MessageDialogComponent } from './message-dialog/message-dialog.component';

import { TopToolbarComponent } from '../../shared/components/top-toolbar/top-toolbar.component';

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
  ],
  templateUrl: './nodes.component.html',
  styleUrl: './nodes.component.scss',
})
export class NodesComponent {
  private readonly api = inject(ApiService);
  private readonly dialog = inject(MatDialog, { optional: true });
  private readonly destroyRef = inject(DestroyRef);

  readonly STATUS_ONLINE = STATUS_ONLINE;
  readonly STATUS_OFFLINE = STATUS_OFFLINE;

  readonly displayedColumns: string[] = [
    'device_id',
    'status',
    'ip_address',
    'capabilities',
    'last_seen',
    'actions',
  ];

  readonly nodesResource = this.api.getNodes();
  readonly statusResource = this.api.getStatus();

  constructor() {
    const timer = setInterval(() => {
      this.nodesResource.reload();
      this.statusResource.reload();
    }, 15000);
    this.destroyRef.onDestroy(() => clearInterval(timer));
  }
  readonly allNodes = computed<Node[]>(() => this.nodesResource.value() ?? []);
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

  async refresh(): Promise<void> {
    await this.api.refresh([this.nodesResource, this.statusResource]);
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
