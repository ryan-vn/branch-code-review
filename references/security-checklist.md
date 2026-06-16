# Security Review Checklist

Run this when the branch touches auth, user input, secrets, crypto, file/network IO, dependencies, admin tools, or multi-tenant data.

Start from `Security Pattern Hints` in `work/branch-review-context.md` when available. Confirm each hint in source — automated scans produce false positives.

## Secrets And Sensitive Data

- Hardcoded API keys, tokens, passwords, private keys, connection strings.
- Secrets logged to stdout, error reports, analytics, or client-visible responses.
- `.env`, credentials, or key files committed or referenced incorrectly.
- PII collected/stored without need; sensitive fields returned in API list endpoints.
- Debug endpoints or verbose error messages exposing stack traces or internal IDs in production paths.

## Authentication And Authorization

- New route/handler missing auth middleware or permission check.
- IDOR: resource accessed by ID without ownership/tenant check.
- Privilege escalation: role/scope check uses client-supplied value.
- Session/token validation bypassed on alternate code path (webhook, internal flag, GraphQL field).
- JWT: `alg=none`, weak secret, missing expiry, audience/issuer not verified.

## Injection And Unsafe Parsing

- SQL/NoSQL built via string concatenation or unparameterized queries.
- Command injection via shell, `exec`, `spawn`, template evaluation.
- XSS: unescaped user content in HTML, `dangerouslySetInnerHTML`, `v-html`, `{@html}`.
- Path traversal in file read/write/upload/download.
- SSRF: user-controlled URL fetched server-side without blocklist.
- Unsafe deserialization: `pickle`, `yaml.load` (non-SafeLoader), `eval`, `Function()`.

## Crypto And Randomness

- Home-grown crypto; MD5/SHA1 for security-sensitive use; static IV/salt.
- `Math.random()` for tokens, IDs, or security decisions.
- Secrets compared with `==` instead of constant-time compare (where relevant).

## Dependencies And Supply Chain

- New dependency with install/postinstall scripts — verify necessity and source.
- Typosquatting risk; duplicate package doing what an existing dep already does.
- Major version bump with breaking security defaults.
- Lockfile missing or out of sync with manifest.

## Frontend Security

- `postMessage` without origin check; sensitive data in `localStorage` without consideration.
- Open redirect in login/callback URLs.
- CSRF: state-changing request without token/same-site protection where required.

## Infrastructure And Config

- Dockerfile runs as root unnecessarily; secrets in build args or env baked into image.
- CORS widened to `*` with credentials.
- TLS verification disabled (`rejectUnauthorized: false`, `InsecureSkipVerify`).
- New public bucket/storage ACL; overly broad IAM policy.

## When To Escalate To Security Review

Use the `review-security` skill when:

- Hints include possible secrets or dangerous APIs in production paths.
- Auth, crypto, upload, or admin surfaces changed.
- New external integration or OAuth flow added.
- You are unsure whether a pattern is exploitable.

Report confirmed issues as P0/P1 when they enable data loss, account takeover, or secret exposure.
