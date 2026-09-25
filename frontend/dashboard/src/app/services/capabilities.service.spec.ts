import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { CapabilitiesService, METRIC_PALETTE } from './capabilities.service';
import { API_BASE_URL } from './api.service';
import { SensorCapability } from '../models/api.models';

describe('CapabilitiesService', () => {
  let service: CapabilitiesService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: '/api' },
        CapabilitiesService,
      ],
    });
    service = TestBed.inject(CapabilitiesService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    TestBed.resetTestingModule();
  });

  it('should be created with empty capabilities signal initially', () => {
    expect(service).toBeTruthy();
    expect(service.capabilities()).toEqual([]);
    expect(service.isLoading()).toBe(false);
  });

  it('should be totally agnostic to metric types: return empty metrics when no capabilities exist', () => {
    expect(service.metrics()).toEqual([]);
  });

  it('should initialize httpResource on init and resolve capabilities', async () => {
    const mockCaps: SensorCapability[] = [
      { key: 'temperature', unit: 'Cel' },
      { key: 'humidity', unit: '%RH' },
    ];

    const capsResource = service.init();
    expect(capsResource).toBeTruthy();
    TestBed.flushEffects();

    const req = httpMock.expectOne('/api/capabilities');
    expect(req.request.method).toBe('GET');
    req.flush(mockCaps);

    await vi.waitFor(() => {
      expect(service.capabilities()).toEqual(mockCaps);
      expect(service.isLoading()).toBe(false);
    });

    // Calling init again returns the existing resource without new HTTP requests
    const secondResource = service.init();
    expect(secondResource).toBe(capsResource);
    httpMock.expectNone('/api/capabilities');
  });

  it('should assign 10 colors alphabetically based on metric name', () => {
    const mockCaps: SensorCapability[] = [
      { key: 'temperature', unit: 'Cel' },
      { key: 'humidity', unit: '%RH' },
      { key: 'light', unit: '%' },
      { key: 'air_quality', unit: 'AQI' },
    ];
    service.setCapabilities(mockCaps);

    const metrics = service.metrics();
    expect(metrics.length).toBe(4);

    // Alphabetical order:
    // 0: air_quality
    // 1: humidity
    // 2: light
    // 3: temperature
    const airQuality = metrics.find((m) => m.id === 'air_quality')!;
    const humidity = metrics.find((m) => m.id === 'humidity')!;
    const light = metrics.find((m) => m.id === 'light')!;
    const temperature = metrics.find((m) => m.id === 'temperature')!;

    expect(airQuality.color).toBe(METRIC_PALETTE[0]);
    expect(humidity.color).toBe(METRIC_PALETTE[1]);
    expect(light.color).toBe(METRIC_PALETTE[2]);
    expect(temperature.color).toBe(METRIC_PALETTE[3]);

    // Test label formatting is completely agnostic
    expect(airQuality.label).toBe('Air Quality');
    expect(airQuality.unit).toBe('AQI');
  });

  it('should maintain stable assigned colors regardless of input order', () => {
    const orderA: SensorCapability[] = [
      { key: 'temperature', unit: 'Cel' },
      { key: 'humidity', unit: '%RH' },
    ];
    const orderB: SensorCapability[] = [
      { key: 'humidity', unit: '%RH' },
      { key: 'temperature', unit: 'Cel' },
    ];

    service.setCapabilities(orderA);
    const tempColorA = service.metrics().find((m) => m.id === 'temperature')!.color;
    const humColorA = service.metrics().find((m) => m.id === 'humidity')!.color;

    service.setCapabilities(orderB);
    const tempColorB = service.metrics().find((m) => m.id === 'temperature')!.color;
    const humColorB = service.metrics().find((m) => m.id === 'humidity')!.color;

    expect(tempColorA).toBe(tempColorB);
    expect(humColorA).toBe(humColorB);
  });

  it('should handle unknown metrics with arbitrary units', () => {
    const mockCaps: SensorCapability[] = [
      { key: 'soil_moisture', unit: 'cb' },
      { key: 'radiation_level', unit: 'uSv/h' },
    ];
    service.setCapabilities(mockCaps);

    const metrics = service.metrics();
    expect(metrics.length).toBe(2);

    const soil = metrics.find((m) => m.id === 'soil_moisture')!;
    expect(soil.label).toBe('Soil Moisture');
    expect(soil.unit).toBe('cb');

    const rad = metrics.find((m) => m.id === 'radiation_level')!;
    expect(rad.label).toBe('Radiation Level');
    expect(rad.unit).toBe('uSv/h');
  });

  describe('getMetricConfig', () => {
    it('should resolve metric config with correct label, unit, and palette color', () => {
      service.setCapabilities([
        { key: 'temperature', unit: 'Cel' },
        { key: 'humidity', unit: '%RH' },
      ]);

      const config = service.getMetricConfig('temperature');
      expect(config.id).toBe('temperature');
      expect(config.label).toBe('Temperature');
      expect(config.unit).toBe('°C');
      expect(METRIC_PALETTE).toContain(config.color);
    });

    it('should resolve aliased metric keys (temp -> temperature)', () => {
      service.setCapabilities([
        { key: 'temperature', unit: 'Cel' },
      ]);

      const config = service.getMetricConfig('temp');
      expect(config.id).toBe('temperature');
      expect(config.unit).toBe('°C');
    });

    it('should dynamically create config using METRIC_PALETTE for unknown metrics when list is empty', () => {
      service.setCapabilities([]);

      const config = service.getMetricConfig('barometric_pressure');
      expect(config.id).toBe('barometric_pressure');
      expect(config.label).toBe('Barometric Pressure');
      expect(METRIC_PALETTE).toContain(config.color);
    });
  });
});
