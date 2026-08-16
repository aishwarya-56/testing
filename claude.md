# CLAUDE.md

## Project

This repository implements a motor insurance surveyor dispatch engine.

The system receives a motor accident notification containing:

- claim_id
- accident latitude
- accident longitude
- city
- province
- event timestamp

It finds eligible motor claim surveyors and recommends/notifies surveyors
according to configurable dispatch tiers.

The first-cut implementation uses Haversine distance.

A future phase will add road-route distance and ETA.

---

# Primary objective

Build a production-quality first-cut Python application that can:

1. Receive accident/claim requests through FastAPI.
2. Validate the request.
3. Persist the received request and dispatch state.
4. Obtain current surveyor locations/status.
5. Filter surveyors based on:
   - availability
   - shift timing
   - location freshness
   - surveyor type
   - geographic radius
6. Calculate Haversine distance.
7. Sort candidates by distance.
8. Select the configurable number of surveyors for each tier.
9. Send simulated notifications.
10. Wait for configurable acceptance timeout.
11. Progress from one tier to the next when:
    - no candidates exist, or
    - candidates were notified but nobody accepted within the timeout.
12. Stop dispatch when a surveyor accepts.
13. Persist the full dispatch history.
14. Provide APIs to inspect dispatch state/history.
15. Produce structured logs and audit information.
16. Support concurrent API requests safely.
17. Have comprehensive automated tests.

---

# Business rules

## Tier 1

- Radius: configurable, default 10 km
- Surveyor types: INTERNAL
- Notification count: configurable, default 1
- Acceptance timeout: configurable, default 120 seconds

Select the closest eligible internal surveyor(s).

---

## Tier 2

- Radius: configurable, default 15 km
- Surveyor types: INTERNAL
- Notification count: configurable, default 5
- Acceptance timeout: configurable, default 60 seconds

Select the closest eligible internal surveyors.

---

## Tier 3

- Radius: configurable, default 15 km
- Surveyor types:
  - INTERNAL
  - OUTSOURCE
- Notification count: configurable, default 5
- Acceptance timeout: configurable, default 60 seconds

Select the closest eligible surveyors regardless of type.

There is NO preference for INTERNAL in Tier 3.

The combined INTERNAL + OUTSOURCE candidate set must be sorted
by distance and the closest N selected.

---

# Tier progression

For each claim:

Tier 1
    |
    | candidate exists
    v
notify
    |
    | accepted
    v
DONE

If no candidate:
    immediately move to Tier 2.

If candidates exist but nobody accepts before timeout:
    move to Tier 2.

Tier 2 follows the same behavior.

Tier 3 follows the same behavior.

If Tier 3 expires or has no candidates:
    mark dispatch as NO_SURVEYOR_ACCEPTED.

Do not wait for a timeout when a tier has zero eligible candidates.

---

# Surveyor eligibility

A surveyor is eligible only if:

1. availability == AVAILABLE
2. current location exists
3. location timestamp is fresh
4. current time is within surveyor shift
5. surveyor type is allowed by current tier
6. Haversine distance <= configured tier radius

Do not implement skill matching in the first version.

Do not implement severity-based skill matching in the first version.

---

# Distance

The first version must use Haversine distance.

Distance must be calculated in kilometers.

All candidate selection must be based on ascending distance.

Do not use straight-line approximations other than Haversine.

The routing abstraction must be designed so that a road routing provider
can later replace Haversine without changing the dispatch engine.

---

# Future routing

Create a routing interface such as:

    RoutingService

with:

    calculate_distance(...)
    calculate_eta(...)

The first implementation is:

    HaversineRoutingService

Do not call external routing APIs in the first-cut implementation.

A future implementation may use:

- OSRM
- Google Routes
- Mapbox
- HERE
- another routing engine

The dispatch engine must depend on the interface, not the concrete provider.

---

# Configuration

Business configuration must live in:

    config/dispatch.yml

Example:

dispatch:
  max_location_age_seconds: 120

  tiers:
    1:
      radius_km: 10
      notify_count: 1
      wait_seconds: 120
      surveyor_types:
        - INTERNAL

    2:
      radius_km: 15
      notify_count: 5
      wait_seconds: 60
      surveyor_types:
        - INTERNAL

    3:
      radius_km: 15
      notify_count: 5
      wait_seconds: 60
      surveyor_types:
        - INTERNAL
        - OUTSOURCE

Never hard-code these business values inside the dispatch algorithm.

---

# Persistence

The application must persist:

## Received request

Store:

- claim_id
- accident details
- request timestamp
- correlation/request ID

## Dispatch state

Store:

- claim_id
- current tier
- status
- notified surveyors
- accepted surveyor
- accepted tier
- dispatch start time
- completion time

## Candidate computation

For every evaluated tier store:

- tier
- radius
- eligible surveyor count
- candidates considered
- rejection reasons/counts
- distance for candidates
- selected candidates
- computation duration

## Notifications

Store:

- claim_id
- tier
- surveyor_id
- surveyor type
- distance
- notification timestamp
- notification status

## Acceptance

Store:

- claim_id
- surveyor_id
- tier
- acceptance timestamp

For local development provide an in-memory repository.

Provide a Redis repository implementation behind an interface.

Do not couple the dispatch engine directly to Redis.

---

# Idempotency

claim_id identifies a dispatch request.

Repeated POST requests for the same active claim must NOT create a second
dispatch workflow or send duplicate notifications.

Return the existing dispatch state for duplicate requests.

Design storage so this can later be implemented atomically using Redis.

---

# Concurrency

The application must safely handle concurrent requests for different claims.

Multiple requests for the same claim must not create duplicate dispatches.

Use per-claim locking or an equivalent concurrency mechanism.

Never hold an asyncio lock while performing a long sleep.

Timeout handling must not block other claims.

Avoid global locks around the dispatch engine.

---

# API

Implement:

POST /api/v1/claims/dispatch

Starts dispatch and returns the currently active tier and selected candidates.

GET /api/v1/claims/{claim_id}

Returns current dispatch state.

GET /api/v1/claims/{claim_id}/history

Returns dispatch/tier/audit history.

POST /api/v1/claims/{claim_id}/accept

Accepts the claim for a surveyor.

GET /health

Returns service health.

GET /ready

Returns readiness.

---

# Initial POST response

If Tier 1 candidates exist, POST /dispatch must immediately return:

- claim_id
- status
- current_tier
- selected surveyors
- distance
- acceptance timeout

Example:

{
  "claim_id": "CLM001",
  "status": "WAITING_FOR_ACCEPTANCE",
  "current_tier": 1,
  "notified_surveyors": [
    {
      "surveyor_id": "S001",
      "type": "INTERNAL",
      "distance_km": 1.23
    }
  ],
  "acceptance_timeout_seconds": 120
}

If Tier 1 has no candidates, evaluate Tier 2 immediately.

Do not return before a candidate is found or all tiers have been exhausted.

---

# Notifications

For the first-cut implementation notification sending is simulated.

Create a NotificationService interface.

The local implementation should log:

[NOTIFICATION]
claim=CLM001
tier=1
surveyor=S001
type=INTERNAL
distance=1.23km

The dispatch engine must not depend on print statements.

Use Python logging.

---

# Logging

Use structured logging.

Every request must have a request_id/correlation_id.

Logs should include where applicable:

- timestamp
- request_id
- claim_id
- tier
- surveyor_id
- surveyor_type
- distance
- status
- elapsed_ms

Important events:

- request received
- request validation
- duplicate request
- dispatch started
- tier started
- surveyor filtering
- candidate count
- candidate selected
- notification sent
- acceptance received
- tier timeout
- tier transition
- dispatch completed
- no surveyor accepted
- errors

Do not log sensitive personal information.

---

# Performance

The first-cut implementation must be capable of processing the core
candidate selection in milliseconds for 50-100 surveyors.

Do not perform network routing calls in the first version.

Haversine calculations should be local CPU operations.

Do not introduce an optimization library unless it is actually required.

This is a ranking/selection problem, not an optimization problem requiring
OR-Tools in the first version.

---

# Testing

Provide unit and integration tests.

Minimum unit tests:

1. Haversine distance calculation.
2. Zero-distance calculation.
3. Radius filtering.
4. Availability filtering.
5. Shift filtering.
6. Location freshness filtering.
7. Internal-only Tier 1.
8. Internal-only Tier 2.
9. Internal + outsource Tier 3.
10. Closest N selection.
11. Configurable notification count.
12. No candidate in Tier 1 immediately advances to Tier 2.
13. No candidate in Tier 2 immediately advances to Tier 3.
14. Timeout advances to next tier.
15. Acceptance stops dispatch.
16. Acceptance from notified surveyor succeeds.
17. Acceptance from non-notified surveyor fails.
18. Duplicate dispatch does not create another workflow.
19. Concurrent requests for different claims.
20. Concurrent requests for the same claim.

Integration tests:

1. POST dispatch.
2. GET claim.
3. POST acceptance.
4. Full Tier 1 -> Tier 2 -> Tier 3 flow.
5. No-surveyor scenario.
6. Duplicate request scenario.

Tests must not depend on real time sleeps where avoidable.

Use dependency injection/fake clocks for timeout testing.

---

# Code quality

Use:

- Python 3.11+
- FastAPI
- Pydantic
- pytest
- pytest-asyncio
- PyYAML
- standard logging

Use type hints throughout.

Prefer small functions/classes.

Avoid giant functions.

Avoid global mutable state except where explicitly encapsulated.

Use dataclasses or Pydantic models for domain objects.

Do not swallow exceptions.

Add useful error messages.

---

# Architecture rule

Keep these concerns separate:

API
    ->
Dispatch Engine
    ->
Candidate Selector
    ->
Geo/Distance Service

Dispatch Engine
    ->
Surveyor Repository

Dispatch Engine
    ->
Notification Service

Dispatch Engine
    ->
Dispatch State Repository

The dispatch engine must not know whether the repository is:

- memory
- Redis
- another database

---

# First-cut scope

DO implement:

- FastAPI
- YAML configuration
- Haversine distance
- surveyor filtering
- tier selection
- notification simulation
- acceptance
- timeout progression
- state persistence abstraction
- in-memory implementation
- structured logging
- audit/history
- tests
- concurrency protection

DO NOT implement yet:

- Kafka
- real Redis integration
- external routing API
- route matrix
- ETA
- skill matching
- severity matching
- optimization solver
- authentication
- UI
- database migrations

Create interfaces/placeholders for future integration where appropriate.

---

# Development workflow

Before changing code:

1. Inspect the existing repository.
2. Understand current architecture.
3. Preserve working behavior unless it conflicts with this specification.
4. Make small, coherent changes.
5. Run tests after changes.
6. Run lint/type checks if configured.
7. Do not claim a feature is complete unless tests pass.

When implementing a feature, add or update tests in the same change.

---

# Definition of done

The first-cut project is complete when:

    pytest

passes all tests and the following manual scenario works:

1. POST a claim.
2. Receive Tier 1 candidate immediately.
3. Do not accept.
4. Tier 1 timeout occurs.
5. Tier 2 candidates are notified.
6. Do not accept.
7. Tier 2 timeout occurs.
8. Tier 3 candidates are notified.
9. Accept one Tier 3 candidate.
10. Dispatch becomes ACCEPTED.
11. Full history is available through API.
12. Logs contain request, tier, candidate, notification and acceptance data.

The implementation must be understandable by another engineer without
requiring knowledge of this conversation.