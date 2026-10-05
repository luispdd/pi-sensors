import { Component, computed, effect, inject, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../../services/api.service';
import { WebSocketService } from '../../../services/websocket.service';
import { LiveStatusItem } from '../../../models/api.models';

@Component({
  selector: 'app-live-controls',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './live-controls.component.html',
  styleUrl: './live-controls.component.scss',
})
export class LiveControlsComponent {
  private readonly api = inject(ApiService);
  private readonly wsService = inject(WebSocketService, { optional: true });

  readonly liveChanged = output<void>();

  readonly liveStatusResource = this.api.getLiveStatus();

  readonly isChecking = computed<boolean>(() => {
    if (this.api.hasCheckedLiveStatus && !this.api.hasCheckedLiveStatus()) return true;
    return (this.api.isCheckingLiveStatus?.() ?? false) && !this.isLiveActive();
  });
  readonly isLiveActive = computed<boolean>(() => {
    if (this.api.isLiveActive) return this.api.isLiveActive();
    return (this.liveStatusResource.value() ?? []).length > 0;
  });
  readonly liveStatusList = computed<LiveStatusItem[]>(() => {
    const list = this.api.liveStatusItems ? this.api.liveStatusItems() : [];
    if (list.length > 0) return list;
    return this.liveStatusResource.value() ?? [];
  });
  readonly activeRateSec = computed<number | null>(() => {
    const rateMs = this.api.activeLiveRateMs ? this.api.activeLiveRateMs() : null;
    if (rateMs) return Math.round(rateMs / 1000);
    const list = this.liveStatusList();
    if (list.length === 0) return null;
    return Math.round(list[0].rate_ms / 1000);
  });

  readonly rateInput = signal<string>('5');
  readonly validationError = signal<string | null>(null);
  readonly resultMessage = this.api.liveResultMessage ?? signal<{ type: 'success' | 'error'; text: string } | null>(null);
  readonly isSubmitting = signal<boolean>(false);

  constructor() {
    effect(() => {
      const activeRate = this.activeRateSec();
      if (activeRate !== null && !this.isSubmitting()) {
        this.rateInput.set(String(activeRate));
      }
    });

    effect(() => {
      if (this.isLiveActive()) {
        this.wsService?.connect?.();
      } else if (this.api.hasCheckedLiveStatus ? this.api.hasCheckedLiveStatus() : true) {
        this.wsService?.disconnect?.();
      }
    });
  }

  onRateInputChange(value: string): void {
    this.rateInput.set(value);
    if (this.validationError()) {
      this.validateRate();
    }
  }

  private validateRate(): number | null {
    const raw = this.rateInput().trim();
    if (!raw) {
      this.validationError.set('Refresh rate is required.');
      return null;
    }
    const num = Number(raw);
    if (isNaN(num) || !Number.isInteger(num) || num <= 0) {
      this.validationError.set('Refresh rate must be a positive integer in seconds (e.g. 1, 5, 10).');
      return null;
    }
    this.validationError.set(null);
    return num;
  }

  async startLive(): Promise<void> {
    const rateSec = this.validateRate();
    if (rateSec === null) {
      return;
    }

    const rateMs = rateSec * 1000;
    this.isSubmitting.set(true);
    this.resultMessage.set(null);
    try {
      const response = await this.api.startLive(rateMs);
      const successful = response.results.filter((r) => r.status === 'success').length;
      const total = response.results.length;
      this.resultMessage.set({
        type: 'success',
        text: `Live streaming started at ${rateSec}s (${successful}/${total} nodes active).`,
      });
      const activeList: LiveStatusItem[] = response.results
        .filter((r) => r.status === 'success')
        .map((r) => ({ device_id: r.device_id, rate_ms: rateMs, started_at: new Date().toISOString() }));
      this.api.liveStatusItems.set(activeList);
      this.liveStatusResource.reload();
      this.wsService?.connect?.();
      this.liveChanged.emit();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'error' in err && (err as { error: { error?: string } }).error?.error
          ? (err as { error: { error?: string } }).error.error
          : 'Failed to start live streaming.';
      this.resultMessage.set({
        type: 'error',
        text: String(msg),
      });
    } finally {
      this.isSubmitting.set(false);
    }
  }

  async stopLive(): Promise<void> {
    this.validationError.set(null);
    this.isSubmitting.set(true);
    this.resultMessage.set(null);
    try {
      const response = await this.api.stopLive();
      const stopped = response.results.filter((r) => r.status === 'success').length;
      const total = response.results.length;
      this.resultMessage.set({
        type: 'success',
        text: `Live streaming stopped (${stopped}/${total} nodes halted).`,
      });
      this.api.liveStatusItems.set([]);
      this.liveStatusResource.reload();
      this.wsService?.disconnect?.();
      this.liveChanged.emit();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'error' in err && (err as { error: { error?: string } }).error?.error
          ? (err as { error: { error?: string } }).error.error
          : 'Failed to stop live streaming.';
      this.resultMessage.set({
        type: 'error',
        text: String(msg),
      });
    } finally {
      this.isSubmitting.set(false);
    }
  }
}
