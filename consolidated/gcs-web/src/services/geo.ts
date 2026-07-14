/**
 * Shared geographic constants for the GCS. Home + metres-per-degree were duplicated
 * across Dashboard and Missions; keep them in one place so they can't drift.
 * (Matches the backend's HOME + M_PER_DEG_* in serve.py.)
 */
export const HOME_LAT = 32.0853;
export const HOME_LON = 34.7818;
export const M_PER_DEG_LAT = 111320;
export const M_PER_DEG_LON = 111320 * Math.cos((HOME_LAT * Math.PI) / 180);

/** lat/lon degrees -> local ENU metres relative to home. */
export const llToEnu = (lat: number, lon: number) => ({
  e: (lon - HOME_LON) * M_PER_DEG_LON,
  n: (lat - HOME_LAT) * M_PER_DEG_LAT,
});
