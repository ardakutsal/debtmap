# Security Policy

## Reporting a vulnerability

Please report security issues privately via
[GitHub Security Advisories](https://github.com/ardakutsal/debtmap/security/advisories/new)
— not in public issues.

You can expect an initial response within a few days.

## Scope notes

- The scanner never executes analyzed code (AST/regex only) — anything that
  achieves code execution from repository content is critical.
- GitHub tokens submitted for private repos are Fernet-encrypted at rest and
  purged one hour after analysis completes. Anything that extends token
  lifetime or exposure is in scope.
- The hosted instance enforces per-IP rate limits, repo size caps, and queue
  depth caps; bypasses are in scope.
