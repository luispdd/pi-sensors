import { Service, InjectionToken, inject, signal, EnvironmentInjector, DestroyRef } from '@angular/core';
import { Observable, Subject } from 'rxjs';
import { Reading } from '../models/api.models';

export type WsConnectionStatus = 'connected' | 'disconnected' | 'connecting';

export const WS_URL = new InjectionToken<string>('WS_URL', {
  factory: () => {
    if (typeof window === 'undefined') return 'ws://127.0.0.1:8000/api/ws';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/api/ws`;
  },
});

@Service()
export class WebSocketService {
  private readonly wsUrl = inject(WS_URL);
  private readonly envInjector = inject(EnvironmentInjector);

  private socket: WebSocket | null = null;
  private readonly readingsSubject = new Subject<Reading>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isDestroyed = false;

  readonly status = signal<WsConnectionStatus>('disconnected');
  readonly readings$: Observable<Reading> = this.readingsSubject.asObservable();

  constructor() {
    const rootDestroyRef = this.envInjector.get(DestroyRef, null, { optional: true });
    if (rootDestroyRef) {
      rootDestroyRef.onDestroy(() => {
        this.isDestroyed = true;
        this.disconnect();
      });
    }
  }

  connect(): void {
    if (this.isDestroyed || typeof WebSocket === 'undefined') return;
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.status.set('connecting');
    try {
      this.socket = new WebSocket(this.wsUrl);

      this.socket.onopen = () => {
        this.status.set('connected');
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.socket.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (data && typeof data === 'object' && 'device_id' in data && 'timestamp' in data && 'metrics' in data) {
            this.readingsSubject.next(data as Reading);
          }
        } catch (e) {
          console.warn('[ws] Failed to parse message:', event.data, e);
        }
      };

      this.socket.onclose = () => {
        this.status.set('disconnected');
        this.socket = null;
        this.scheduleReconnect();
      };

      this.socket.onerror = (err) => {
        console.warn('[ws] WebSocket error:', err);
        if (this.socket) {
          try {
            this.socket.close();
          } catch {
            // Ignore error on close
          }
        }
      };
    } catch (err) {
      console.warn('[ws] Could not create WebSocket:', err);
      this.status.set('disconnected');
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.isDestroyed || this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.onerror = null;
      this.socket.onmessage = null;
      this.socket.onopen = null;
      try {
        this.socket.close();
      } catch {
        // Ignore
      }
      this.socket = null;
    }
    this.status.set('disconnected');
  }
}
