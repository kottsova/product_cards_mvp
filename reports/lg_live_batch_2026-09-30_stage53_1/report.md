# Stage 53.1 - live LG queue and progress

## Diagnosis

- The original port 8765 process was PID 27328, started at 16:40:03 local time, before HEAD 8177b022 (16:45:07). Its exact loaded commit was not recorded by the process; fce3438b was the last commit available at startup.
- The embedded worker was active. Its directory lock was held, and the production SQLite recorded the first claim one second after enqueue. Each following job started automatically after the previous job finished.
- The batch page rendered a static snapshot and had only a manual GET refresh link. A page left open after enqueue continued to show 12 queued even while the worker progressed. No dequeue, brand filter, max-worker or stale-running blocker was found.
- The active worker shares data/batches.sqlite3 with the UI. The job table has no per-row claimed/locked/worker-id columns; the directory-wide lock is data/worker.lock.
- No old runtime exception log was available. The new runtime startup log has no exception. All 12 production jobs reached a terminal state.

## Preserved production jobs

Batch 8a4f36c0777f4ecc8578d8eaa6a4cf6f (test.xlsx); all timestamps below are local UTC+4. Created at 17:11:16.

| Job ID | Article | Status | Started | Finished |
|---|---|---|---|---|
| c7f724f1b00f49acad9122177ae7621b | P12ED.NSAR + P12ED.USAR | needs_review | 17:11:17 | 17:11:40 |
| 85aa063f5a154cadadf1bdda14a9145c | S3WER.ALWPCOM | done | 17:11:40 | 17:12:51 |
| 50ccf0b8ed5a48c1a73661b2e47486ca | MS2082F | needs_review | 17:12:52 | 17:13:02 |
| cd6677cc7a5c44a48a08a3b248336d80 | TW4V7EB1W | needs_review | 17:13:02 | 17:13:28 |
| 0ad917e208bd4e789bf43ca0d3473bde | GC-B459MLWM.ADSQCIS | needs_review | 17:13:29 | 17:14:11 |
| e0bbfc3b286541cd9c4566750e647989 | VK89309H | done | 17:14:11 | 17:15:05 |
| 1fbff9ed4f624605a6e8d78900ed7d69 | W4W8LVPKZHM.APBPCOM | needs_review | 17:15:05 | 17:16:26 |
| a51e6184f0244d1fbb131e27517998c3 | 86NANO81A6A | done | 17:16:27 | 17:17:01 |
| e5740c9c9f6d47dc8a55ca769b910891 | RNC9.DRUSLLK | done | 17:17:01 | 17:17:37 |
| 2759038f79b44a94a12daf164fe809c9 | S40T | done | 17:17:37 | 17:18:02 |
| 5dd7e0a817514ce08c2f5e7d17f0cd58 | ON66 | done | 17:18:02 | 17:18:26 |
| 5c54a8e85c004151994444e0b93c8774 | ON77DKDRUSLLK | done | 17:18:26 | 17:18:56 |

- All 12 existing jobs remain. No duplicate job was created and no product was replayed during this stage.
- Final UI counts: selected 12, queued 0, running 0, completed 12, review 10. Job status totals: done 7, needs_review 5. Review includes finished jobs whose cards still have evidence gaps.

## Fix and runtime

- batch.html now polls the existing read-only batch GET every five seconds while selected jobs are queued/running. It updates the four progress counts plus each LG row job/card status without touching selection checkboxes or posting work. The manual refresh link remains a GET.
- Production SQLite was backed up with sqlite3.Connection.backup to ignored data/backups/stage53_1_before_restart.sqlite3 before restart.
- Restarted the local app from this workspace with uvicorn in a hidden process. Parent PID 26416, listener PID 1292, port 8765. Startup completed; embedded worker reacquired data/worker.lock. GET of the current batch returned HTTP 200 and included the new poller.
- After restart: 12 batch jobs, 0 active jobs, integrity_check=ok, foreign-key violations=0.
- Working DB hash is pinned as a record of the owner-uploaded batch and worker results. The DB is ignored by Git and is not part of the commit.

## Validation

- Targeted offline LG batch/embedded worker tests: 12 passed.
- Full offline regression: 1,352 tests passed in 714.905 seconds (python -m unittest discover -s tests -p test_*.py -q). The test suite blocks real network I/O; an expected logged blocked-request trace is not a test failure.
- git diff --check: passed before final review.
