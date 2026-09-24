// File edit conflict detection.
// Compares file hash at load time vs current time to detect out-of-band modifications.
// Prevents silent data loss when user edits a field while file is modified externally.

export interface EditConflictDetector {
  recordFileHash(hash: string): void;
  updateFileHash(hash: string): void;
  detectConflict(currentHash: string): boolean;
  getLastFileHash(): string | null;
}

export function createEditConflictDetector(): EditConflictDetector {
  let loadedHash: string | null = null;

  return {
    recordFileHash(hash) {
      loadedHash = hash;
    },

    updateFileHash(hash) {
      loadedHash = hash;
    },

    detectConflict(currentHash) {
      return loadedHash !== null && loadedHash !== currentHash;
    },

    getLastFileHash() {
      return loadedHash;
    }
  };
}
