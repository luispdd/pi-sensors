import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';
import { LayoutComponent } from './layout.component';

@Component({
  template: '<div data-testid="home-view">Home Content</div>',
  standalone: true,
})
class MockHomeComponent {}

@Component({
  template: '<div data-testid="nodes-view">Nodes Content</div>',
  standalone: true,
})
class MockNodesComponent {}

@Component({
  template: '<div data-testid="graphs-view">Graphs Content</div>',
  standalone: true,
})
class MockGraphsComponent {}

describe('LayoutComponent', () => {
  let fixture: ComponentFixture<LayoutComponent>;
  let component: LayoutComponent;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LayoutComponent],
      providers: [
        provideRouter([
          { path: '', component: MockHomeComponent },
          { path: 'nodes', component: MockNodesComponent },
          { path: 'graphs', component: MockGraphsComponent },
        ]),
      ],
    }).compileComponents();

    router = TestBed.inject(Router);
    fixture = TestBed.createComponent(LayoutComponent);
    component = fixture.componentInstance;
    await router.initialNavigation();
    fixture.detectChanges();
  });

  it('should create layout component', () => {
    expect(component).toBeTruthy();
  });

  it('should render 56px fixed icon rail with navigation items', () => {
    const rail = fixture.nativeElement.querySelector('[data-testid="icon-rail"]');
    expect(rail).toBeTruthy();
    expect(rail.className).toContain('w-14'); // 14 * 4px = 56px
    expect(rail.className).toContain('fixed');

    const homeNav = fixture.nativeElement.querySelector('[data-testid="nav-home"]');
    const nodesNav = fixture.nativeElement.querySelector('[data-testid="nav-nodes"]');
    const graphsNav = fixture.nativeElement.querySelector('[data-testid="nav-graphs"]');

    expect(homeNav).toBeTruthy();
    expect(nodesNav).toBeTruthy();
    expect(graphsNav).toBeTruthy();
  });

  it('should swap views in router outlet when navigating between routes', async () => {
    // Initially on Home route '/'
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[data-testid="home-view"]')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('[data-testid="nodes-view"]')).toBeFalsy();

    // Navigate to /nodes
    await router.navigateByUrl('/nodes');
    fixture.detectChanges();
    await fixture.whenStable();

    expect(fixture.nativeElement.querySelector('[data-testid="home-view"]')).toBeFalsy();
    expect(fixture.nativeElement.querySelector('[data-testid="nodes-view"]')).toBeTruthy();

    // Navigate to /graphs
    await router.navigateByUrl('/graphs');
    fixture.detectChanges();
    await fixture.whenStable();

    expect(fixture.nativeElement.querySelector('[data-testid="nodes-view"]')).toBeFalsy();
    expect(fixture.nativeElement.querySelector('[data-testid="graphs-view"]')).toBeTruthy();
  });
});
