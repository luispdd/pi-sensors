import { Component, computed, input } from '@angular/core';
import { CommonModule } from '@angular/common';

export const STATUS_ONLINE = 'online';
export const STATUS_OFFLINE = 'offline';

export const STATUS_LABEL_ONLINE = 'ONLINE';
export const STATUS_LABEL_OFFLINE = 'OFFLINE';

export type StatusValue = typeof STATUS_ONLINE | typeof STATUS_OFFLINE | string;

@Component({
  selector: 'app-status-pill',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './status-pill.component.html',
  styleUrl: './status-pill.component.scss',
})
export class StatusPillComponent {
  readonly status = input<StatusValue>(STATUS_OFFLINE);
  readonly label = input<string | undefined>(undefined);

  readonly isOnline = computed(() => {
    const s = this.status();
    return typeof s === 'string' && s.trim().toLowerCase() === STATUS_ONLINE;
  });

  readonly displayText = computed(() => {
    const customLabel = this.label();
    if (customLabel !== undefined && customLabel !== null) {
      return customLabel;
    }
    return this.isOnline() ? STATUS_LABEL_ONLINE : STATUS_LABEL_OFFLINE;
  });

  readonly onlineClasses = 'bg-success-bg text-success-fg border border-success-fg/30';
  readonly offlineClasses = 'bg-danger-bg text-danger-fg border border-danger-fg/30';
}
