import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  MessageDialogComponent,
  MessageDialogData,
  DIALOG_STATUS_SUCCESS,
  DIALOG_STATUS_ERROR,
} from './message-dialog.component';
import { ApiService } from '../../../services/api.service';

describe('MessageDialogComponent', () => {
  let fixture: ComponentFixture<MessageDialogComponent>;
  let component: MessageDialogComponent;

  const mockDialogData: MessageDialogData = {
    node: {
      device_id: 'display-node-01',
      ip_address: '192.168.1.50',
      capabilities: ['display'],
      last_seen: new Date().toISOString(),
    },
  };

  const mockDialogRef = {
    close: vi.fn(),
  };

  const mockApiService = {
    postDisplay: vi.fn(),
  };

  beforeEach(async () => {
    vi.clearAllMocks();

    await TestBed.configureTestingModule({
      imports: [MessageDialogComponent],
      providers: [
        { provide: MatDialogRef, useValue: mockDialogRef },
        { provide: MAT_DIALOG_DATA, useValue: mockDialogData },
        { provide: ApiService, useValue: mockApiService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(MessageDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should validate message emptiness and max length', () => {
    expect(component.isValid()).toBe(false);

    component.messageText.set('   ');
    expect(component.isValid()).toBe(false);

    component.messageText.set('Hello Node');
    expect(component.isValid()).toBe(true);

    component.messageText.set('a'.repeat(129));
    expect(component.isValid()).toBe(false);
  });

  it('should call ApiService.postDisplay on send and handle success', async () => {
    vi.useFakeTimers();
    mockApiService.postDisplay.mockResolvedValue({ status: 'success' });

    component.messageText.set('Test message');
    const sendPromise = component.send();

    expect(mockApiService.postDisplay).toHaveBeenCalledWith('display-node-01', 'Test message');
    expect(component.isSubmitting()).toBe(true);

    await sendPromise;
    expect(component.status()).toBe(DIALOG_STATUS_SUCCESS);
    expect(component.isSubmitting()).toBe(false);

    vi.advanceTimersByTime(1300);
    expect(mockDialogRef.close).toHaveBeenCalledWith(true);
  });

  it('should handle API failure gracefully', async () => {
    mockApiService.postDisplay.mockResolvedValue({
      status: 'failed',
      error: 'Device unreachable',
    });

    component.messageText.set('Test message');
    await component.send();

    expect(component.status()).toBe(DIALOG_STATUS_ERROR);
    expect(component.statusMessage()).toContain('Device unreachable');
    expect(mockDialogRef.close).not.toHaveBeenCalled();
  });

  it('should handle unexpected network exceptions', async () => {
    mockApiService.postDisplay.mockRejectedValue(new Error('Network error'));

    component.messageText.set('Test message');
    await component.send();

    expect(component.status()).toBe(DIALOG_STATUS_ERROR);
    expect(component.statusMessage()).toBe('Network error');
  });

  it('should close dialog when cancel/close is called', () => {
    component.close();
    expect(mockDialogRef.close).toHaveBeenCalledWith(false);
  });
});
