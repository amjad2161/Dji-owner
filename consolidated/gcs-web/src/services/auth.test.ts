import { describe, it, expect } from 'vitest';
import { decodeToken, tokenValid } from './auth';

// Build a JWT-shaped token (base64url header.payload.sig) for the client-side checks.
function makeToken(payload: object): string {
  const b64u = (s: string) => btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `${b64u(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))}.${b64u(JSON.stringify(payload))}.sig`;
}

describe('auth token helpers', () => {
  it('decodes the payload', () => {
    const d = decodeToken(makeToken({ sub: 'admin', role: 'operator', exp: 9999999999 }));
    expect(d?.sub).toBe('admin');
    expect(d?.role).toBe('operator');
  });

  it('treats a future-exp token as valid and a past-exp token as invalid', () => {
    const now = Math.floor(Date.now() / 1000);
    expect(tokenValid(makeToken({ exp: now + 3600 }))).toBe(true);
    expect(tokenValid(makeToken({ exp: now - 10 }))).toBe(false);
  });

  it('rejects malformed tokens', () => {
    expect(decodeToken('not-a-token')).toBeNull();
    expect(tokenValid('garbage')).toBe(false);
    expect(tokenValid('')).toBe(false);
  });
});
