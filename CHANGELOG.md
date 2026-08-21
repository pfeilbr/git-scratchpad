# Changelog

Notable changes to `gsuite-cli`. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); the project uses
[semantic versioning](https://semver.org/).

## 0.1.0

First release. One command-line tool for Google Workspace, drawing its
command surface from Google's [`gws`](https://github.com/googleworkspace/cli)
and steipete's [`gog`](https://github.com/openclaw/gogcli) and keeping the
latter's one-command login. **18 services, 149 commands, zero runtime
dependencies** (Python ≥ 3.10 standard library only).

Coverage against those two is measured, not claimed: `scripts/parity.py`
compares this CLI's parser tree with both projects' own published command
lists. At this release that is 10 of gws's 19 in-scope helper verbs and 97 of
gog's 545 — the daily-driver commands, not the long tail. The gap is listed
per command in `parity/`, and CI fails if it widens.

### Services

- **Mail and calendar** — `gmail` (search, read, threads, attachments, send,
  reply, forward, triage verbs, labels, drafts, vacation, signature, filters,
  batch-modify), `calendar` (calendars, events, agenda, create, update,
  respond, free/busy).
- **Files and documents** — `drive` (list, search, upload, download, export,
  share, permissions, move, trash/restore, link-sharing audit, shared
  drives), `docs`, `sheets` (values plus tab management), `slides`.
- **People and messaging** — `contacts` (including contact groups), `tasks`,
  `chat` (spaces, members, threaded replies), `keep` (notes and sharing),
  `meet` (spaces, conference records, participants), `forms`.
- **Administration** — `admin` (Directory users, groups, org units).
- **Reporting** — `searchconsole` (sites, search analytics, URL inspection),
  `analytics` (GA4 properties, reports, realtime).
- **Escape hatches** — `api` (authorized call to any Google API, plus
  Discovery browsing) and `completion` (bash/zsh, generated from the parser).
- **Cross-service** — `workflow` (standup report, meeting prep, weekly
  digest, email-to-task, file announce): each command composes two or more of
  the APIs above into one answer, and names every service it needs when one
  of them is not authorized.

### Authentication

- `auth login` runs a loopback OAuth flow: browser opens, you approve, done.
  The account email is auto-detected; tokens are stored per account at mode
  `0600` and refreshed automatically.
- Multiple accounts with aliases (`-a work`), `switch`, `doctor`.
- Other credential sources: `$GSUITE_ACCESS_TOKEN` and Application Default
  Credentials. Service-account keys are deliberately unsupported (RS256
  signing would require a third-party dependency) and fail with a clear
  message.
- `auth logout` revokes the grant at Google before removing anything local,
  so a recovered copy of the token file is useless; `--no-revoke` opts out and
  `auth revoke` rotates a credential without dropping the account.
- Config lives at `$GSUITE_CONFIG_DIR`, else `%APPDATA%\gsuite` on Windows,
  else `$XDG_CONFIG_HOME/gsuite`, else `~/.config/gsuite`.

### Output and safety

- Aligned tables by default; `--json`, `--csv`, and `--fields` to select
  columns; `--debug` traces HTTP metadata to stderr without leaking bodies or
  the bearer token; `--timeout SECONDS` (or `GSUITE_TIMEOUT`) caps each
  request.
- `--readonly` refuses any non-GET at the single client chokepoint, before
  credentials are even resolved.
- Transient failures retry with 1/2/4s backoff honoring `Retry-After`: a 429
  for any command, a 5xx only for reads and idempotent writes. A `POST` or
  `PATCH` that hits a 5xx is never replayed, since the request may already
  have been applied. A 401 forces one token refresh and retry.
- Filesystem paths the user names (`--attach`, `upload`, `-o`) report a
  missing file or unwritable destination as an error, not a traceback.
- API errors keep Google's wording and add the next step — a scope failure
  names the service and the exact `auth login` command to run.
- Exits like a UNIX filter: quiet on a closed pipe, `1` for operational
  errors, `2` for usage errors, `130` on interrupt. Network failures (DNS,
  refused connections, TLS, timeouts) are `error:` lines, never tracebacks.

### Correctness and hardening

- Dates resolve in the local timezone (or `--tz`): day bounds were computed
  at UTC midnight, so `agenda` showed the wrong window everywhere but UTC.
  Timed events now carry an explicit `timeZone`.
- Values interpolated into Drive `q` queries are escaped (backslash first,
  then quote), so a folder id or search term containing a quote can no longer
  change the query's meaning.
- Ids interpolated into URL paths are percent-encoded, so a `?`, `#` or space
  can no longer end the path early. Single-segment ids (spreadsheet, document,
  file, form, task list) escape `/` too; multi-segment resource names
  (`spaces/AAAA`, `people/c123`) keep `/` and instead refuse `.`/`..`
  segments, which could otherwise walk up into a different API path.
- Header values containing a line break are refused with a named error;
  previously a trailing newline was silently encoded into a corrupt address
  and sent.
- Credential files are *created* `0600` inside `0700` directories rather than
  tightened afterwards, and every write is atomic (`os.replace`), so an
  interrupted run cannot leave an unparseable `accounts.json`.
- `api call` keeps repeated `--param` keys and prints non-JSON replies
  instead of raising.
- A success response whose body is not JSON — a captive portal's sign-in
  page, a proxy's block notice, a gateway's plain-text `ok` — is reported as
  an error naming the status, the host and the first line of what arrived.
  Previously only `api call` survived it; every other command raised
  `JSONDecodeError`.
- Dates that are not `YYYY-MM-DD` (`agenda --date tomorrow`,
  `freebusy --from "next week"`) and non-numeric `sheets rm-tab --tab`
  values are named errors rather than tracebacks, and are rejected before
  anything is sent.

### Engineering

- Built strictly red-green: every change proved failing before it was
  implemented.
- Three gates. `scripts/verify.py` compiles, runs the full suite, and fails
  on stale generated docs. `scripts/smoke.py` installs the project into a
  throwaway virtualenv and drives the real console script, including genuine
  request round-trips against a loopback server. `scripts/fuzz_cli.py` drives
  every command with hostile input — 5960 fixed, deterministic cases — and
  fails on any traceback, which is how the three fixes above were found. All
  three run in CI.
- The command reference and the README's command table are generated from the
  CLI's own parser tree, so documentation cannot drift from the code.
