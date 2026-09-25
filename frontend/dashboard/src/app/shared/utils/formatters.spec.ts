import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { computedUptime, formatRemainingTime, formatUptime } from './formatters';

describe('formatters utility', () => {
  describe('formatUptime', () => {
    it('should return "0h 0m" for 0 seconds', () => {
      expect(formatUptime(0)).toBe('0h 0m');
    });

    it('should return "0h 0m" for null and undefined', () => {
      expect(formatUptime(null)).toBe('0h 0m');
      expect(formatUptime(undefined)).toBe('0h 0m');
    });

    it('should return "0h 0m" for negative seconds', () => {
      expect(formatUptime(-100)).toBe('0h 0m');
    });

    it('should return "0h 5m" for 300 seconds', () => {
      expect(formatUptime(300)).toBe('0h 5m');
    });

    it('should return "1h 0m" for 3600 seconds', () => {
      expect(formatUptime(3600)).toBe('1h 0m');
    });

    it('should return "2h 30m" for 9000 seconds', () => {
      expect(formatUptime(9000)).toBe('2h 30m');
    });

    it('should handle fractional seconds by flooring', () => {
      expect(formatUptime(3665.9)).toBe('1h 1m');
    });
  });

  describe('computedUptime', () => {
    it('should reactively compute formatted uptime from a signal source', () => {
      TestBed.runInInjectionContext(() => {
        const uptimeSig = signal<number | undefined>(undefined);
        const formatted = computedUptime(() => uptimeSig());

        expect(formatted()).toBe('0h 0m');

        uptimeSig.set(7200);
        expect(formatted()).toBe('2h 0m');

        uptimeSig.set(7320);
        expect(formatted()).toBe('2h 2m');
      });
    });
  });

  describe('formatRemainingTime', () => {
    it('should format full minutes and seconds', () => {
      expect(formatRemainingTime(300)).toBe('5m 00s');
      expect(formatRemainingTime(272)).toBe('4m 32s');
      expect(formatRemainingTime(65)).toBe('1m 05s');
    });

    it('should format seconds when less than 1 minute', () => {
      expect(formatRemainingTime(45)).toBe('45s');
      expect(formatRemainingTime(5)).toBe('5s');
    });

    it('should return "Due now" for 0 seconds or negative', () => {
      expect(formatRemainingTime(0)).toBe('Due now');
      expect(formatRemainingTime(-10)).toBe('Due now');
    });

    it('should return "—" for null or undefined', () => {
      expect(formatRemainingTime(null)).toBe('—');
      expect(formatRemainingTime(undefined)).toBe('—');
    });
  });
});
