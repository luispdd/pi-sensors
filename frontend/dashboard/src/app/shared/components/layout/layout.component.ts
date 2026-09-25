import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

export interface NavItem {
  path: string;
  label: string;
  icon: string;
  exact: boolean;
}

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.scss',
})
export class LayoutComponent {
  readonly navItems: NavItem[] = [
    { path: '/', label: 'Home', icon: 'dashboard', exact: true },
    { path: '/nodes', label: 'Nodes', icon: 'sensors', exact: false },
    { path: '/graphs', label: 'Graphs', icon: 'show_chart', exact: false },
  ];
}
