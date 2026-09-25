import { Component } from '@angular/core';
import { LayoutComponent } from './shared/components/layout/layout.component';

@Component({
  imports: [LayoutComponent],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {}
