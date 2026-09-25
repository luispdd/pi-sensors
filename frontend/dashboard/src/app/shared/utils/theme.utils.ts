/**
 * Utility for resolving CSS variables at runtime for charting libraries (like ApexCharts)
 * which require concrete hex/rgb values for SVG strokes and canvas gradient math.
 */

/**
 * Resolves a CSS variable value from document.documentElement at runtime.
 * Falls back to defaultValue if running in SSR, headless tests, or if the variable is not set.
 *
 * @param cssVar The CSS variable name (e.g., '--metric-temperature' or 'accent').
 * @param fallback The fallback hex or rgb color string.
 * @returns The resolved color string.
 */
export function getThemeColor(cssVar: string, fallback: string): string {
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    const varName = cssVar.startsWith('--') ? cssVar : `--${cssVar}`;
    const val = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    if (val) {
      return val;
    }
  }
  return fallback;
}
