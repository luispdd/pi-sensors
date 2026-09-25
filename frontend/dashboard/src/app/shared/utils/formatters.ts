import { Signal, computed } from '@angular/core';

/**
 * Formats an uptime duration in seconds into a human-readable "Xh Ym" string.
 *
 * @param uptimeSeconds Total elapsed seconds (or null/undefined).
 * @returns Formatted uptime string, e.g. "2h 30m" or "0h 0m".
 */
export function formatUptime(uptimeSeconds: number | null | undefined): string {
  const sec = Math.max(0, Math.floor(uptimeSeconds ?? 0));
  const hrs = Math.floor(sec / 3600);
  const mins = Math.floor((sec % 3600) / 60);
  return `${hrs}h ${mins}m`;
}

/**
 * Reusable computed signal creator for formatted uptime.
 *
 * @param source Reactive getter returning the number of uptime seconds.
 * @returns Computed signal returning the formatted uptime string.
 */
export function computedUptime(source: () => number | null | undefined): Signal<string> {
  return computed(() => formatUptime(source()));
}

/**
 * Formats remaining seconds until next sync/refresh into a readable "Xm Ys" or "Xs" string.
 *
 * @param remainingSeconds Number of remaining seconds (or null/undefined).
 * @returns Formatted remaining time, e.g. "4m 32s", "45s", or "Due now".
 */
export function formatRemainingTime(remainingSeconds: number | null | undefined): string {
  if (remainingSeconds === null || remainingSeconds === undefined || isNaN(remainingSeconds)) {
    return '—';
  }
  const sec = Math.max(0, Math.floor(remainingSeconds));
  if (sec === 0) {
    return 'Due now';
  }
  const mins = Math.floor(sec / 60);
  const remSec = sec % 60;
  if (mins === 0) {
    return `${remSec}s`;
  }
  return `${mins}m ${remSec.toString().padStart(2, '0')}s`;
}
