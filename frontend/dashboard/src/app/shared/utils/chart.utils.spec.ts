import { describe, expect, it } from 'vitest';
import {
  BOARD_PALETTE,
  getBoardColor,
  METRIC_PALETTE,
  assignMetricColors,
  extractMetricValue,
  groupByDevice,
} from './chart.utils';
import { Reading } from '../../models/api.models';

describe('chart.utils', () => {
  describe('BOARD_PALETTE & getBoardColor', () => {
    it('should contain the same 10 colors as METRIC_PALETTE', () => {
      expect(BOARD_PALETTE).toEqual(METRIC_PALETTE);
      expect(BOARD_PALETTE.length).toBe(10);
    });

    it('should cycle colors using modulo', () => {
      expect(getBoardColor(0)).toBe(METRIC_PALETTE[0]);
      expect(getBoardColor(1)).toBe(METRIC_PALETTE[1]);
      expect(getBoardColor(9)).toBe(METRIC_PALETTE[9]);
      expect(getBoardColor(10)).toBe(METRIC_PALETTE[0]);
      expect(getBoardColor(11)).toBe(METRIC_PALETTE[1]);
    });
  });

  describe('METRIC_PALETTE & assignMetricColors', () => {
    it('should define a 10-color metric palette', () => {
      expect(METRIC_PALETTE.length).toBe(10);
      expect(new Set(METRIC_PALETTE).size).toBe(10);
    });

    it('should assign colors to metrics in alphabetical order', () => {
      const keys = ['temperature', 'humidity', 'air_quality'];
      const map = assignMetricColors(keys);

      // Alphabetical: air_quality (0), humidity (1), temperature (2)
      expect(map.get('air_quality')).toBe(METRIC_PALETTE[0]);
      expect(map.get('humidity')).toBe(METRIC_PALETTE[1]);
      expect(map.get('temperature')).toBe(METRIC_PALETTE[2]);
    });
  });

  describe('extractMetricValue', () => {
    it('should extract arbitrary unknown metrics directly without hardcoded rules', () => {
      expect(extractMetricValue({ pressure: 1013.25 }, 'pressure')).toBe(1013.3);
      expect(extractMetricValue({ co2: 450 }, 'co2')).toBe(450);
      expect(extractMetricValue({ radiation: 0.15 }, 'radiation')).toBe(0.2);
    });

    it('should resolve temperature aliases (temp <-> temperature)', () => {
      expect(extractMetricValue({ temp: 22.4 }, 'temperature')).toBe(22.4);
      expect(extractMetricValue({ temperature: 23.1 }, 'temp')).toBe(23.1);
      expect(extractMetricValue({ temperature: 23.1 }, 'temperature')).toBe(23.1);
    });

    it('should resolve humidity aliases (hum <-> humidity)', () => {
      expect(extractMetricValue({ hum: 45.2 }, 'humidity')).toBe(45.2);
      expect(extractMetricValue({ humidity: 50.0 }, 'hum')).toBe(50.0);
      expect(extractMetricValue({ humidity: 50.0 }, 'humidity')).toBe(50.0);
    });

    it('should resolve light aliases (light <-> light_pct)', () => {
      expect(extractMetricValue({ light_pct: 88.5 }, 'light')).toBe(88.5);
      expect(extractMetricValue({ light: 92.0 }, 'light_pct')).toBe(92.0);
      expect(extractMetricValue({ light: 92.0 }, 'light')).toBe(92.0);
    });

    it('should return undefined for missing or invalid metrics', () => {
      expect(extractMetricValue(undefined, 'temp')).toBeUndefined();
      expect(extractMetricValue({}, 'temp')).toBeUndefined();
      expect(extractMetricValue({ temp: NaN }, 'temp')).toBeUndefined();
    });
  });

  describe('groupByDevice', () => {
    it('should return an empty map for empty readings', () => {
      const result = groupByDevice([], 'temperature');
      expect(result.size).toBe(0);
    });

    it('should group readings by device_id for unknown metrics', () => {
      const readings: Reading[] = [
        {
          id: 1,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'pico-01',
          metrics: { co2: 420 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
        {
          id: 2,
          timestamp: '2026-09-24T12:05:00Z',
          device_id: 'pico-01',
          metrics: { co2: 435 },
          ingested_at: '2026-09-24T12:05:05Z',
        },
        {
          id: 3,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'pico-02',
          metrics: { co2: 410 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
      ];

      const result = groupByDevice(readings, 'co2');
      expect(result.size).toBe(2);
      expect(result.get('pico-01')!.length).toBe(2);
      expect(result.get('pico-02')!.length).toBe(1);
    });

    it('should group readings by device_id with alias resolution', () => {
      const readings: Reading[] = [
        {
          id: 1,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'pico-1w-01',
          metrics: { temp: 20.5 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
        {
          id: 2,
          timestamp: '2026-09-24T12:05:00Z',
          device_id: 'pico-1w-01',
          metrics: { temperature: 21.0 },
          ingested_at: '2026-09-24T12:05:05Z',
        },
        {
          id: 3,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'pico-2w-01',
          metrics: { temp: 19.8 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
      ];

      const result = groupByDevice(readings, 'temperature');
      expect(result.size).toBe(2);

      const dev1Points = result.get('pico-1w-01')!;
      expect(dev1Points).toBeDefined();
      expect(dev1Points.length).toBe(2);
      expect(dev1Points[0].y).toBe(20.5);
      expect(dev1Points[1].y).toBe(21.0);

      const dev2Points = result.get('pico-2w-01')!;
      expect(dev2Points).toBeDefined();
      expect(dev2Points.length).toBe(1);
      expect(dev2Points[0].y).toBe(19.8);
    });

    it('should sort points chronologically regardless of input order', () => {
      const readings: Reading[] = [
        {
          id: 3,
          timestamp: '2026-09-24T12:10:00Z',
          device_id: 'node-01',
          metrics: { hum: 60.0 },
          ingested_at: '2026-09-24T12:10:05Z',
        },
        {
          id: 1,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'node-01',
          metrics: { humidity: 50.0 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
        {
          id: 2,
          timestamp: '2026-09-24T12:05:00Z',
          device_id: 'node-01',
          metrics: { hum: 55.0 },
          ingested_at: '2026-09-24T12:05:05Z',
        },
      ];

      const result = groupByDevice(readings, 'humidity');
      const points = result.get('node-01')!;

      expect(points.length).toBe(3);
      expect(points[0].x).toBe(new Date('2026-09-24T12:00:00Z').getTime());
      expect(points[0].y).toBe(50.0);
      expect(points[1].x).toBe(new Date('2026-09-24T12:05:00Z').getTime());
      expect(points[1].y).toBe(55.0);
      expect(points[2].x).toBe(new Date('2026-09-24T12:10:00Z').getTime());
      expect(points[2].y).toBe(60.0);
    });

    it('should average duplicate timestamps for the same device', () => {
      const readings: Reading[] = [
        {
          id: 1,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'node-01',
          metrics: { light_pct: 70 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
        {
          id: 2,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'node-01',
          metrics: { light: 80 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
      ];

      const result = groupByDevice(readings, 'light');
      const points = result.get('node-01')!;

      expect(points.length).toBe(1);
      expect(points[0].y).toBe(75.0);
    });

    it('should omit devices that have no points for the requested metric', () => {
      const readings: Reading[] = [
        {
          id: 1,
          timestamp: '2026-09-24T12:00:00Z',
          device_id: 'node-temp-only',
          metrics: { temp: 22.0 },
          ingested_at: '2026-09-24T12:00:05Z',
        },
      ];

      const result = groupByDevice(readings, 'light');
      expect(result.size).toBe(0);
    });
  });
});
