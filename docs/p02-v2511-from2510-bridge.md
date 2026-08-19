# P02 · VF Library V2.5.10 → V2.5.11 Production Bridge

OWNER authenticated Production screenshot at 2026-08-19 15:56 +08:00 shows current V2.5.10 and latest V2.5.11, with the UpdateService correctly failing closed because V2.5.10 was not yet in the verified direct-source contract.

This runner creates a source-specific bridge asset from immutable V2.5.10 to the already-published immutable V2.5.11 target source, verifies a real existing-data UpdateCore upgrade with backup/data/favorite/session/Scratch preservation and SQLite integrity/FK, publishes only the new source-specific bridge asset to the existing V2.5.11 Release, and performs remote bytes/SHA/atomic-identity readback.

Production write: NO.
