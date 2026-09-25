import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  StatusPillComponent,
  STATUS_ONLINE,
  STATUS_LABEL_ONLINE,
  STATUS_LABEL_OFFLINE,
} from './status-pill.component';

describe('StatusPillComponent', () => {
  let fixture: ComponentFixture<StatusPillComponent>;
  let component: StatusPillComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StatusPillComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(StatusPillComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render offline state by default', () => {
    fixture.detectChanges();

    const pill = fixture.nativeElement.querySelector('[data-testid="status-pill"]');
    const text = fixture.nativeElement.querySelector('[data-testid="status-text"]');
    const dot = fixture.nativeElement.querySelector('[data-testid="status-dot"]');

    expect(text.textContent.trim()).toBe(STATUS_LABEL_OFFLINE);
    expect(pill.className).toContain('bg-danger-bg');
    expect(pill.className).toContain('text-danger-fg');
    expect(dot.className).toContain('bg-danger-fg');
  });

  it('should render online state with pulse dot and success colors', () => {
    fixture.componentRef.setInput('status', STATUS_ONLINE);
    fixture.detectChanges();

    const pill = fixture.nativeElement.querySelector('[data-testid="status-pill"]');
    const text = fixture.nativeElement.querySelector('[data-testid="status-text"]');
    const dot = fixture.nativeElement.querySelector('[data-testid="status-dot"]');

    expect(text.textContent.trim()).toBe(STATUS_LABEL_ONLINE);
    expect(pill.className).toContain('bg-success-bg');
    expect(pill.className).toContain('text-success-fg');
    expect(dot.className).toContain('bg-success-fg');
    expect(dot.className).toContain('animate-pulse');
  });

  it('should render custom label when provided', () => {
    fixture.componentRef.setInput('status', STATUS_ONLINE);
    fixture.componentRef.setInput('label', 'CONNECTED');
    fixture.detectChanges();

    const text = fixture.nativeElement.querySelector('[data-testid="status-text"]');
    expect(text.textContent.trim()).toBe('CONNECTED');
  });
});
