import { describe, expect, it, afterEach } from 'vitest';
import { getThemeColor } from './theme.utils';

describe('theme.utils', () => {
  afterEach(() => {
    document.documentElement.style.removeProperty('--test-color');
  });

  it('should return fallback if CSS variable is not set', () => {
    expect(getThemeColor('--test-color', '#2DD4BF')).toBe('#2DD4BF');
  });

  it('should resolve CSS variable when set on document.documentElement', () => {
    document.documentElement.style.setProperty('--test-color', '#F09595');
    expect(getThemeColor('--test-color', '#2DD4BF')).toBe('#F09595');
  });

  it('should prepend -- prefix if omitted', () => {
    document.documentElement.style.setProperty('--test-color', '#38BDF8');
    expect(getThemeColor('test-color', '#2DD4BF')).toBe('#38BDF8');
  });
});
