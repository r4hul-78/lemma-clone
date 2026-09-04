# Issue 18 and Issue 19 Resolution

## Issue 18 — Inefficient API Polling

The dashboard polls `/api/v1/status/{job_id}` every second. This is simple, but it can generate unnecessary HTTP requests while a long-running plagiarism analysis is still processing.

### Fix

The frontend API configuration layer now wraps status requests with a small resilient transport layer. Repeated one-second polling ticks are coalesced and served from the latest known status until the next request window. Live requests use exponential backoff from 1.5 seconds up to 5 seconds.

This preserves the existing dashboard polling code while reducing unnecessary backend traffic and keeping the UI responsive.

## Issue 19 — Job Failure Handling

The analysis pipeline can fail during document extraction, online retrieval, matching, or another worker stage. A frontend polling loop must not remain in an apparent processing state when the worker has actually failed, and temporary network errors should not immediately abort a valid job.

### Fix

The status transport now:

- retries transient status-service/network failures;
- keeps the job in a retryable processing state during temporary failures;
- applies an 8-second request timeout;
- limits transport retries to five consecutive failures;
- converts an exhausted retry window into a terminal `failed` status with a user-readable error;
- preserves the backend's existing `completed` and `failed` terminal states.

A regression test also verifies that a Celery `FAILURE` state is exposed by the API as a terminal `failed` response.

## Verification

Run the backend suite with:

```powershell
.\venv\Scripts\python.exe -m pytest backend/tests/
```

The frontend configuration file was additionally checked for JavaScript syntax errors with Node.js.
