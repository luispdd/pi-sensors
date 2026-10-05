import {
  Service,
  InjectionToken,
  inject,
  signal,
  computed,
  effect,
  EnvironmentInjector,
  runInInjectionContext,
} from '@angular/core';
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
  LiveStatusItem,
  LiveStartResponse,
  LiveStopResponse,
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
  private readonly injector = inject(EnvironmentInjector);
  readonly baseUrl = inject(API_BASE_URL);
  private readonly registeredResources = new Set<ReloadableResource>();

  private sharedStatusResource?: HttpResourceRef<SystemStatus | undefined>;
  private sharedLiveStatusResource?: HttpResourceRef<LiveStatusItem[]>;
  private readonly liveStatusResourceRef = signal<HttpResourceRef<LiveStatusItem[]> | null>(null);

  // App-level notification banner state that persists across navigation
  readonly liveResultMessage = signal<{ type: 'success' | 'error'; text: string } | null>(null);

  // App-level System Status Caching & Request Lifecycle State
  private readonly statusReloadTrigger = signal(0);
  private lastKnownStatus?: SystemStatus;
  private lastStatusReloadTime = 0;

  readonly systemStatus = computed<SystemStatus | undefined>(() => {
    const val = this.getStatus().value();
    if (val) {
      this.lastKnownStatus = val;
      return val;
    }
    return this.lastKnownStatus;
  });

  cachedStatus(): SystemStatus | undefined {
    return this.lastKnownStatus;
  }

  /**
   * Reloads /api/status if not requested within minDebounceMs (default 1000ms).
   * Ensures status is refreshed on page loads without firing multiple requests
   * when several components mount simultaneously on the same view.
   */
  reloadStatus(minDebounceMs: number = 1000): void {
    const now = Date.now();
    if (now - this.lastStatusReloadTime < minDebounceMs) {
      return;
    }
    this.lastStatusReloadTime = now;
    if (this.sharedStatusResource) {
      this.statusReloadTrigger.update((v) => v + 1);
      this.sharedStatusResource.reload();
    } else {
      this.getStatus();
    }
  }

  // App-level Live Monitoring Status State
  readonly hasCheckedLiveStatus = signal<boolean>(false);
  readonly isCheckingLiveStatus = signal<boolean>(false);
  readonly liveStatusItems = signal<LiveStatusItem[]>([]);

  readonly isLiveActive = computed<boolean>(() => {
    if (this.liveStatusItems().length > 0) return true;
    const ref = this.liveStatusResourceRef();
    const res = ref ? ref.value() ?? [] : [];
    return res.length > 0;
  });

  readonly activeLiveRateMs = computed<number | null>(() => {
    const list = this.liveStatusItems();
    if (list.length > 0 && list[0].rate_ms > 0) return list[0].rate_ms;
    const ref = this.liveStatusResourceRef();
    const res = ref ? ref.value() ?? [] : [];
    return res.length > 0 && res[0].rate_ms > 0 ? res[0].rate_ms : null;
  });


  /**
   * Performs GET /api/live/status to check and update live monitoring status.
   * Ensures the request is performed and status is stored in the service.
   */
  async checkLiveStatus(force: boolean = false): Promise<LiveStatusItem[]> {
    if (this.hasCheckedLiveStatus() && !force && !this.isCheckingLiveStatus()) {
      return this.liveStatusItems();
    }
    this.isCheckingLiveStatus.set(true);
    try {
      const items = await firstValueFrom(
        this.http.get<LiveStatusItem[]>(`${this.baseUrl}/live/status`)
      );
      const list = items ?? [];
      this.liveStatusItems.set(list);
      this.hasCheckedLiveStatus.set(true);
      return list;
    } catch (err) {
      this.hasCheckedLiveStatus.set(true);
      throw err;
    } finally {
      this.isCheckingLiveStatus.set(false);
    }
  }

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
   * Creates a reactive HttpResourceRef for GET /api/status (shared singleton instance bound to root injector)
   */
  getStatus(): HttpResourceRef<SystemStatus | undefined> {
    if (!this.sharedStatusResource) {
      this.lastStatusReloadTime = Date.now();
      this.sharedStatusResource = runInInjectionContext(this.injector, () =>
        httpResource<SystemStatus | undefined>(() => {
          this.statusReloadTrigger();
          return `${this.baseUrl}/status`;
        })
      );
      this.registeredResources.add(this.sharedStatusResource);
    }
    return this.sharedStatusResource;
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
          if (params.is_fine_tuned !== undefined) {
            searchParams.set('is_fine_tuned', params.is_fine_tuned.toString());
          }
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
   * Creates a reactive HttpResourceRef for GET /api/live/status (shared singleton instance bound to root injector)
   */
  getLiveStatus(): HttpResourceRef<LiveStatusItem[]> {
    if (!this.sharedLiveStatusResource) {
      runInInjectionContext(this.injector, () => {
        this.sharedLiveStatusResource = httpResource<LiveStatusItem[]>(
          () => `${this.baseUrl}/live/status`,
          {
            defaultValue: [],
          }
        );
        this.registeredResources.add(this.sharedLiveStatusResource);
        this.liveStatusResourceRef.set(this.sharedLiveStatusResource);

        effect(() => {
          const res = this.sharedLiveStatusResource;
          if (!res) return;
          const loading = res.isLoading();
          this.isCheckingLiveStatus.set(loading);
          const st = res.status();
          if (st === 'resolved' || st === 'error') {
            this.hasCheckedLiveStatus.set(true);
            const val = res.value();
            if (val) {
              this.liveStatusItems.set(val);
            }
          }
        });
      });
    }
    return this.sharedLiveStatusResource!;
  }

  /**
   * Starts live monitoring across discovered nodes via POST /api/live/start
   */
  startLive(rate_ms: number, broker?: string): Promise<LiveStartResponse> {
    const body: { rate_ms: number; broker?: string } = { rate_ms };
    if (broker) body.broker = broker;
    return firstValueFrom(this.http.post<LiveStartResponse>(`${this.baseUrl}/live/start`, body));
  }

  /**
   * Stops live monitoring across discovered nodes via POST /api/live/stop
   */
  stopLive(): Promise<LiveStopResponse> {
    return firstValueFrom(this.http.post<LiveStopResponse>(`${this.baseUrl}/live/stop`, {}));
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

