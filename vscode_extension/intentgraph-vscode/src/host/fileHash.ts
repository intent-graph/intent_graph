// Compute SHA-256 hex digest of a string.
// Used by loadGraph.ts (initial fileHash acquisition) and yamlEdit.ts (hash verification).
// Algorithm: SHA-256 (node:crypto createHash). CRLF normalisation applied before hashing
// to avoid Windows false-positive mismatches.

import { createHash } from 'node:crypto';

/**
 * Normalise CRLF → LF, then return SHA-256 hex digest.
 * Both host-side hash computations (load + edit) must use this function
 * so the hash is platform-stable.
 */
export function computeFileHash(content: string): string {
  const normalised = content.replace(/\r\n/g, '\n');
  return createHash('sha256').update(normalised).digest('hex');
}
