import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: 'nodes',
    loadComponent: () =>
      import('./features/nodes/nodes.component').then((m) => m.NodesComponent),
  },
  {
    path: 'graphs',
    loadComponent: () =>
      import('./features/graphs/graphs.component').then((m) => m.GraphsComponent),
  },
];
