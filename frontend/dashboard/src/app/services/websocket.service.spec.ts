import { TestBed } from '@angular/core/testing';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { WebSocketService, WS_URL } from './websocket.service';
import { Reading } from '../models/api.models';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState = 0; // CONNECTING
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((err: any) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  simulateOpen() {
    this.readyState = 1; // OPEN
    if (this.onopen) this.onopen();
  }

  simulateMessage(data: string) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data }));
    }
  }

  simulateClose() {
    this.readyState = 3; // CLOSED
    if (this.onclose) this.onclose();
  }

  simulateError(error: any) {
    if (this.onerror) this.onerror(error);
  }

  close() {
    this.readyState = 3;
    if (this.onclose) this.onclose();
  }
}

describe('WebSocketService', () => {
  let originalWebSocket: any;

  beforeEach(() => {
    MockWebSocket.instances = [];
    originalWebSocket = (globalThis as any).WebSocket;
    (globalThis as any).WebSocket = MockWebSocket as any;
  });

  afterEach(() => {
    (globalThis as any).WebSocket = originalWebSocket;
  });

  it('should not connect in constructor, and connect when connect() is called', () => {
    TestBed.configureTestingModule({
      providers: [
        WebSocketService,
        { provide: WS_URL, useValue: 'ws://test:8000/api/ws' },
      ],
    });

    const service = TestBed.inject(WebSocketService);
    // Initially not connected
    expect(MockWebSocket.instances.length).toBe(0);
    expect(service.status()).toBe('disconnected');

    // Explicit connect
    service.connect();
    expect(MockWebSocket.instances.length).toBe(1);
    expect(MockWebSocket.instances[0].url).toBe('ws://test:8000/api/ws');
    expect(service.status()).toBe('connecting');

    MockWebSocket.instances[0].simulateOpen();
    expect(service.status()).toBe('connected');

    service.disconnect();
    expect(service.status()).toBe('disconnected');
  });

  it('should emit valid reading objects via readings$', () => {
    TestBed.configureTestingModule({
      providers: [
        WebSocketService,
        { provide: WS_URL, useValue: 'ws://test:8000/api/ws' },
      ],
    });

    const service = TestBed.inject(WebSocketService);
    service.connect();
    const mockWs = MockWebSocket.instances[0];
    mockWs.simulateOpen();

    const received: Reading[] = [];
    const sub = service.readings$.subscribe((r) => received.push(r));

    const sampleReading = {
      device_id: 'pico-01',
      timestamp: '2026-10-04T12:00:00Z',
      metrics: { temp: 22.4, humidity: 48.0 },
      is_fine_tuned: true,
    };

    mockWs.simulateMessage(JSON.stringify(sampleReading));

    expect(received.length).toBe(1);
    expect(received[0].device_id).toBe('pico-01');
    expect(received[0].is_fine_tuned).toBe(true);

    // Malformed JSON should not throw or emit
    mockWs.simulateMessage('not valid json');
    expect(received.length).toBe(1);

    // Non-reading object should not emit
    mockWs.simulateMessage(JSON.stringify({ other: 123 }));
    expect(received.length).toBe(1);

    sub.unsubscribe();
    service.disconnect();
  });

  it('should remain connected across component lifecycle (decoupled from component DestroyRef)', () => {
    TestBed.configureTestingModule({
      providers: [
        WebSocketService,
        { provide: WS_URL, useValue: 'ws://test:8000/api/ws' },
      ],
    });

    const service = TestBed.inject(WebSocketService);
    service.connect();
    const mockWs = MockWebSocket.instances[0];
    mockWs.simulateOpen();
    expect(service.status()).toBe('connected');

    // Simulate a component-scoped DestroyRef being destroyed
    const componentDestroyCallbacks: Array<() => void> = [];
    const fakeComponentDestroyRef = {
      onDestroy: (cb: () => void) => componentDestroyCallbacks.push(cb),
      destroy: () => componentDestroyCallbacks.forEach((cb) => cb()),
    };

    fakeComponentDestroyRef.destroy();

    // Service should still be connected because it's tied to root EnvironmentInjector, not component DestroyRef
    expect(service.status()).toBe('connected');
    expect(mockWs.readyState).toBe(1); // OPEN

    service.disconnect();
  });
});
