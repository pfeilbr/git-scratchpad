# gsuite-cli

One command-line tool for all of Google Workspace — `gmail`, `calendar`,
`drive`, `docs`, `sheets`, `slides`, `contacts`, `tasks`, `chat`, `keep`,
`forms`, `meet`, and Workspace `admin` — plus `auth`, a raw `api`
passthrough to **any** Google API via the Discovery service, and `completion`
for shell tab-completion.

It merges the command surfaces of two existing tools and keeps the best
property of each:

| | [`gws`](https://github.com/googleworkspace/cli) (Google) | [`gog`](https://github.com/openclaw/gogcli) (steipete) | `gsuite` |
| --- | --- | --- | --- |
| Service coverage | dynamic, every API | hand-crafted core | hand-crafted core **+** `api call` for everything else |
| Auth UX | heavier GCP setup | one-command login | one-command login, multi-account, aliases |
| Admin / Directory | yes | yes | yes |
| Runtime dependencies | Node toolchain | Go binary | **zero** (Python ≥ 3.10 stdlib) |

## Install

```sh
pip install .            # installs the `gsuite` entry point
python3 -m gsuite.cli    # or run straight from a checkout
```

## Sixty-second start

```console
$ gsuite auth credentials set client_secret.json
OAuth client credentials saved
$ gsuite auth login
Opening browser for Google sign-in…
Logged in as you@example.com (services: calendar, contacts, drive, gmail)
$ gsuite gmail search is:unread --max 3
ID      DATE                    FROM               SUBJECT
19ab3f  Mon, 5 Jan 2026 09:14   alice@example.com  Q1 roadmap
$ gsuite calendar agenda
ID     START                 SUMMARY   LOCATION
e1a2   2026-01-05T09:00:00Z  Standup   Zoom
```

## Where to go next

- **[Authentication guide](guides/authentication.md)** — OAuth client setup,
  multi-account, aliases, headless use.
- **[Command reference](reference/index.md)** — every service and subcommand,
  with options tables and examples (generated from the CLI itself).
- **[Architecture](architecture.md)** — how the pieces fit, with diagrams.
- **[Scripting & automation](guides/scripting.md)** — `--json`, `auth token`,
  `api call`, exit codes.
- **[Development](development.md)** — the red-green workflow and how to add
  a service.

!!! tip "Safe by default in automation"
    Pass `--readonly` (before the service name) and any request that could
    modify data is refused at the client chokepoint — useful for audits,
    cron jobs, and dry runs.
