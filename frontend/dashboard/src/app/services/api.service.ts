import { Service, InjectionToken, inject, signal } from '@angular/core';
import { HttpClient, httpResource, HttpResourceRef } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import {
  Node,
  SystemStatus,
  Reading,
  ReadingsQueryParams,
  SensorCapability,
  DisplayMessageResponse,
  DiscoverResponse,
  SyncResponse,
} from '../models/api.models';

export interface ReloadableResource {
  reload: () => boolean | void;
}

export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  factory: () => '/api',
});

@Service()
export class ApiService {
  private readonly http = inject(HttpClient);
  readonly baseUrl = inject(API_BASE_URL);
  private readonly registeredResources = new Set<ReloadableResource>();

  /**
   * Creates a reactive HttpResourceRef for GET /api/nodes
   */
  getNodes(): HttpResourceRef<Node[]> {
    const res = httpResource<Node[]>(() => `${this.baseUrl}/nodes`, {
      defaultValue: [],
    });
    this.registeredResources.add(res);
    return res;
  }

  /**
   * Creates a reactive HttpResourceRef for GET /api/capabilities
   */
  getCapabilities(): HttpResourceRef<SensorCapability[]> {
    const res = httpResource<SensorCapability[]>(() => `${this.baseUrl}/capabilities`, {
      defaultValue: [],
    });
    this.registeredResources.add(res);
    return res;
  }

  /**
   * Creates a reactive HttpResourceRef for GET /api/status
   */
  getStatus(): HttpResourceRef<SystemStatus | undefined> {
    const res = httpResource<SystemStatus | undefined>(() => `${this.baseUrl}/status`);
    this.registeredResources.add(res);
    return res;
  }

  /**
   * Creates a reactive HttpResourceRef for GET /api/readings with dynamic/reactive query params
   */
  getReadings(paramsFn?: () => ReadingsQueryParams | undefined): HttpResourceRef<Reading[]> {
    const res = httpResource<Reading[]>(
      () => {
        const params = paramsFn ? paramsFn() : undefined;
        const searchParams = new URLSearchParams();
        if (params) {
          if (params.device_id) searchParams.set('device_id', params.device_id);
          if (params.since) searchParams.set('since', params.since);
          if (params.until) searchParams.set('until', params.until);
          if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
        }
        const qs = searchParams.toString();
        return `${this.baseUrl}/readings${qs ? '?' + qs : ''}`;
      },
      { defaultValue: [] }
    );
    this.registeredResources.add(res);
    return res;
  }

  /**
   * Proxies a plain text display message to a board via POST /api/display
   */
  postDisplay(target: string, message: string): Promise<DisplayMessageResponse> {
    return firstValueFrom(
      this.http.post<DisplayMessageResponse>(`${this.baseUrl}/display`, { target, message })
    );
  }

  /**
   * Forces immediate LAN discovery burst via POST /api/discover
   */
  discover(): Promise<DiscoverResponse> {
    return firstValueFrom(this.http.post<DiscoverResponse>(`${this.baseUrl}/discover`, {}));
  }

  /**
   * Triggers on-demand catch-up synchronization via POST /api/sync
   */
  sync(): Promise<SyncResponse> {
    return firstValueFrom(this.http.post<SyncResponse>(`${this.baseUrl}/sync`, {}));
  }

  readonly lastRefreshTimestamp = signal<number>(Date.now());

  /**
   * Centralized refresh method that triggers synchronization with edge nodes
   * and reloads active resources.
   *
   * @param resources Optional array of resources to reload. If omitted, all registered
   *                  resources in ApiService are reloaded.
   */
  async refresh(resources?: ReloadableResource[]): Promise<void> {
    this.lastRefreshTimestamp.set(Date.now());
    try {
      await this.sync();
    } catch {
      // Continue even if sync is already executing or unavailable
    }

    const targets = resources && resources.length > 0 ? resources : Array.from(this.registeredResources);
    for (const res of targets) {
      try {
        res.reload();
      } catch {
        // Continue if resource was already destroyed or encountered error
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 600));
  }
}

