import { describe, it, expect } from 'vitest';
import { HOME_LAT, HOME_LON, M_PER_DEG_LON, llToEnu } from './geo';

describe('geo.llToEnu', () => {
  it('maps home to the ENU origin', () => {
    const o = llToEnu(HOME_LAT, HOME_LON);
    expect(o.e).toBeCloseTo(0, 6);
    expect(o.n).toBeCloseTo(0, 6);
  });

  it('one degree north is ~111320 m', () => {
    expect(llToEnu(HOME_LAT + 1, HOME_LON).n).toBeCloseTo(111320, 0);
  });

  it('east metres use the cos(lat) longitude scale (shrinks with latitude)', () => {
    expect(llToEnu(HOME_LAT, HOME_LON + 1).e).toBeCloseTo(M_PER_DEG_LON, 0);
    expect(M_PER_DEG_LON).toBeLessThan(111320);
  });
});
