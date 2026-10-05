import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LiveControlsComponent } from './live-controls.component';
import { ApiService } from '../../../services/api.service';
import { WebSocketService } from '../../../services/websocket.service';

describe('LiveControlsComponent', () => {
  let fixture: ComponentFixture<LiveControlsComponent>;
  let component: LiveControlsComponent;
  let mockApiService: any;
  let mockWsService: any;
  let liveStatusSignal: any;

  beforeEach(async () => {
    liveStatusSignal = signal<any[]>([]);
    mockApiService = {
      getLiveStatus: vi.fn().mockReturnValue({
        value: liveStatusSignal,
        isLoading: signal(false),
        error: signal(undefined),
        reload: vi.fn(),
      }),
      startLive: vi.fn().mockResolvedValue({
        status: 'ok',
        rate_ms: 1000,
        broker: '192.168.1.100',
        results: [
          { device_id: 'pico-01', status: 'success' },
          { device_id: 'pico-02', status: 'success' },
        ],
      }),
      stopLive: vi.fn().mockResolvedValue({
        status: 'ok',
        results: [
          { device_id: 'pico-01', status: 'success' },
          { device_id: 'pico-02', status: 'success' },
        ],
      }),
      checkLiveStatus: vi.fn().mockImplementation(async () => liveStatusSignal()),
      hasCheckedLiveStatus: signal(true),
      isCheckingLiveStatus: signal(false),
      liveStatusItems: liveStatusSignal,
      isLiveActive: () => liveStatusSignal().length > 0,
      activeLiveRateMs: () => (liveStatusSignal().length > 0 ? liveStatusSignal()[0].rate_ms : null),
    };

    mockWsService = {
      connect: vi.fn(),
      disconnect: vi.fn(),
      status: signal('disconnected'),
    };

    await TestBed.configureTestingModule({
      imports: [LiveControlsComponent],
      providers: [
        { provide: ApiService, useValue: mockApiService },
        { provide: WebSocketService, useValue: mockWsService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LiveControlsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should call startLive with valid rate in seconds and show success result', async () => {
    component.rateInput.set('2');
    fixture.detectChanges();

    const liveChangedSpy = vi.fn();
    component.liveChanged.subscribe(liveChangedSpy);

    const startBtn = fixture.nativeElement.querySelector('[data-testid="start-live-btn"]');
    startBtn.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(mockApiService.startLive).toHaveBeenCalledWith(2000);
    expect(component.validationError()).toBeNull();
    expect(liveChangedSpy).toHaveBeenCalled();

    const resultEl = fixture.nativeElement.querySelector('[data-testid="live-result-message"]');
    expect(resultEl).toBeTruthy();
    expect(resultEl.textContent).toContain('Live streaming started at 2s (2/2 nodes active)');
  });

  it('should block startLive if rate is empty and show validation message', async () => {
    component.rateInput.set('');
    fixture.detectChanges();

    const startBtn = fixture.nativeElement.querySelector('[data-testid="start-live-btn"]');
    startBtn.click();
    fixture.detectChanges();

    expect(mockApiService.startLive).not.toHaveBeenCalled();
    expect(component.validationError()).toBe('Refresh rate is required.');

    const errorEl = fixture.nativeElement.querySelector('[data-testid="live-rate-error"]');
    expect(errorEl).toBeTruthy();
    expect(errorEl.textContent).toContain('Refresh rate is required.');
  });

  it('should block startLive if rate is zero, negative, or not an integer', async () => {
    component.rateInput.set('0');
    fixture.detectChanges();

    const startBtn = fixture.nativeElement.querySelector('[data-testid="start-live-btn"]');
    startBtn.click();
    fixture.detectChanges();

    expect(mockApiService.startLive).not.toHaveBeenCalled();
    expect(component.validationError()).toContain('positive integer');

    component.rateInput.set('-100');
    startBtn.click();
    fixture.detectChanges();
    expect(mockApiService.startLive).not.toHaveBeenCalled();

    component.rateInput.set('abc');
    startBtn.click();
    fixture.detectChanges();
    expect(mockApiService.startLive).not.toHaveBeenCalled();
  });

  it('should call stopLive and show success result', async () => {
    const liveChangedSpy = vi.fn();
    component.liveChanged.subscribe(liveChangedSpy);

    const stopBtn = fixture.nativeElement.querySelector('[data-testid="stop-live-btn"]');
    stopBtn.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(mockApiService.stopLive).toHaveBeenCalled();
    expect(liveChangedSpy).toHaveBeenCalled();

    const resultEl = fixture.nativeElement.querySelector('[data-testid="live-result-message"]');
    expect(resultEl).toBeTruthy();
    expect(resultEl.textContent).toContain('Live streaming stopped (2/2 nodes halted)');
  });

  it('should show error result message if startLive fails', async () => {
    mockApiService.startLive.mockRejectedValue({ error: { error: 'Broker connection refused' } });

    component.rateInput.set('1000');
    await component.startLive();
    fixture.detectChanges();

    const resultEl = fixture.nativeElement.querySelector('[data-testid="live-result-message"]');
    expect(resultEl).toBeTruthy();
    expect(resultEl.textContent).toContain('Broker connection refused');
  });

  it('should show Inactive badge by default when no live nodes exist', () => {
    const inactiveEl = fixture.nativeElement.querySelector('[data-testid="live-inactive-badge"]');
    expect(inactiveEl).toBeTruthy();
    expect(inactiveEl.textContent).toContain('Inactive');
  });

  it('should show Active badge and prefill rateInput when live nodes are active', async () => {
    liveStatusSignal.set([
      { device_id: 'pico-01', rate_ms: 6000, started_at: '2026-10-04T12:00:00Z' },
      { device_id: 'pico-02', rate_ms: 6000, started_at: '2026-10-04T12:00:00Z' },
    ]);
    await fixture.whenStable();
    fixture.detectChanges();

    const activeEl = fixture.nativeElement.querySelector('[data-testid="live-active-badge"]');
    expect(activeEl).toBeTruthy();
    expect(activeEl.textContent).toContain('Active (6s rate • 2 nodes)');
    expect(component.rateInput()).toBe('6');
  });

  it('should show Checking... badge before live status check completes and not mark as Inactive', () => {
    mockApiService.hasCheckedLiveStatus.set(false);
    fixture.detectChanges();

    expect(component.isChecking()).toBe(true);
    const checkingEl = fixture.nativeElement.querySelector('[data-testid="live-checking-badge"]');
    const inactiveEl = fixture.nativeElement.querySelector('[data-testid="live-inactive-badge"]');

    expect(checkingEl).toBeTruthy();
    expect(checkingEl.textContent).toContain('Checking...');
    expect(inactiveEl).toBeFalsy();
  });

  it('should initiate WebSocket connection when startLive is called and disconnect on stopLive', async () => {
    component.rateInput.set('5');
    fixture.detectChanges();

    await component.startLive();
    expect(mockWsService.connect).toHaveBeenCalled();

    await component.stopLive();
    expect(mockWsService.disconnect).toHaveBeenCalled();
  });

  it('should reactively connect/disconnect WebSocket when isLiveActive changes', async () => {
    mockWsService.connect.mockClear();
    mockWsService.disconnect.mockClear();

    // Set live nodes active
    liveStatusSignal.set([{ device_id: 'pico-01', rate_ms: 5000 }]);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(mockWsService.connect).toHaveBeenCalled();

    // Set live nodes inactive
    liveStatusSignal.set([]);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(mockWsService.disconnect).toHaveBeenCalled();
  });

  it('should not prematurely disconnect WebSocket when live status has not been checked yet', async () => {
    mockWsService.disconnect.mockClear();
    mockApiService.hasCheckedLiveStatus.set(false);
    liveStatusSignal.set([]);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(mockWsService.disconnect).not.toHaveBeenCalled();
  });
});
