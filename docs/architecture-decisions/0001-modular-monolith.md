# ADR 0001: Modular Django monolith

Status: Accepted.

The launch application is one Django deployment with domain modules under `app/modules/` and a small TypeScript frontend under `app/frontend/`. PostgreSQL is authoritative. Modules own their tables and mutate them only through their public service functions; direct cross-module model mutation is prohibited.

Permitted dependency direction is: HTTP/views -> owning service -> owning model; domain services may call `operations`, `audit`, and explicit policy APIs. `identity` and `tenancy` are foundational. Recruiting depends on tenancy, never the reverse at runtime. Audit accepts minimized event facts and must not import domain models. Operations contains technical primitives and no hiring policy.

This minimizes deployment and transactional complexity while retaining enforceable boundaries. New services require measured scaling, isolation, or independent-availability evidence and a new ADR.
