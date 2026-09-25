import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TopToolbarComponent } from './top-toolbar.component';
import { ApiService } from '../../../services/api.service';

describe('TopToolbarComponent', () => {
  let fixture: ComponentFixture<TopToolbarComponent>;
  let component: TopToolbarComponent;
  let mockApiService: any;

  beforeEach(async () => {
    mockApiService = {
      getStatus: vi.fn().mockReturnValue({
        value: signal({ uptime_s: 7200 }),
        isLoading: signal(false),
        error: signal(undefined),
        reload: vi.fn(),
      }),
      discover: vi.fn().mockResolvedValue({ discovered_count: 2, nodes: [] }),
      sync: vi.fn().mockResolvedValue({ status: 'ok', total_ingested: 0 }),
      refresh: vi.fn().mockImplementation(async (resources) => {
        await mockApiService.sync();
        resources?.forEach((r: any) => r?.reload?.());
      }),
    };

    await TestBed.configureTestingModule({
      imports: [TopToolbarComponent],
      providers: [{ provide: ApiService, useValue: mockApiService }],
    }).compileComponents();

    fixture = TestBed.createComponent(TopToolbarComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('title', 'Test Page Title');
    fixture.componentRef.setInput('subtitle', 'Test Page Subtitle');
    fixture.detectChanges();
  });

  it('should create and render title and subtitle inputs', () => {
    expect(component).toBeTruthy();
    const titleEl = fixture.nativeElement.querySelector('[data-testid="page-title"]');
    const subtitleEl = fixture.nativeElement.querySelector('[data-testid="page-subtitle"]');
    expect(titleEl.textContent).toContain('Test Page Title');
    expect(subtitleEl.textContent).toContain('Test Page Subtitle');
  });

  it('should format uptime correctly from status resource', () => {
    expect(component.uptimeFormatted()).toBe('2h 0m');
    const uptimeEl = fixture.nativeElement.querySelector('[data-testid="uptime-badge"]');
    expect(uptimeEl.textContent).toContain('2h 0m');
  });

  it('should trigger discover and refresh data on Refresh click', async () => {
    const refreshBtn = fixture.nativeElement.querySelector('[data-testid="refresh-btn"]');
    expect(refreshBtn).toBeTruthy();
    expect(refreshBtn.disabled).toBe(false);
    expect(refreshBtn.textContent).toContain('Refresh');

    const refreshPromise = component.refresh();
    expect(component.isRefreshing()).toBe(true);
    fixture.detectChanges();

    expect(refreshBtn.disabled).toBe(true);
    expect(refreshBtn.textContent).toContain('Refreshing...');
    await refreshPromise;
    expect(mockApiService.discover).toHaveBeenCalledTimes(1);
    expect(mockApiService.refresh).toHaveBeenCalledTimes(1);
    expect(component.isRefreshing()).toBe(false);
  });
});
