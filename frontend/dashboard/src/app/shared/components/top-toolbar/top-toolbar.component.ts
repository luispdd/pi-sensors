import { Component, inject, input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../../services/api.service';
import { computedUptime } from '../../utils/formatters';

@Component({
  selector: 'app-top-toolbar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './top-toolbar.component.html',
  styleUrl: './top-toolbar.component.scss',
})
export class TopToolbarComponent {
  private readonly api = inject(ApiService);

  readonly title = input.required<string>();
  readonly subtitle = input<string>('');

  readonly statusResource = this.api.getStatus();
  readonly isRefreshing = signal<boolean>(false);

  readonly uptimeFormatted = computedUptime(() => this.statusResource.value()?.uptime_s);

  async refresh(): Promise<void> {
    this.isRefreshing.set(true);
    try {
      await this.api.discover();
      await this.api.refresh();
    } catch (err) {
      console.error('Refresh failed:', err);
    } finally {
      this.isRefreshing.set(false);
    }
  }
}
