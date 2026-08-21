# gsuite-cli

One command-line tool for all of Google Workspace — Gmail, Calendar, Drive,
Docs, Sheets, Slides, Contacts, Tasks, Chat, Keep, Forms, Meet, and Workspace
Admin — plus Search Console and Google Analytics reporting, a raw passthrough
to **any** Google API via the Discovery service, and shell completion for the
whole surface.

It draws its command surface from two existing tools:

- [`gws`](https://github.com/googleworkspace/cli) — Google's Workspace CLI
  (dynamic Discovery-driven coverage, admin, generic API calls)
- [`gog`](https://github.com/openclaw/gogcli) — steipete's Workspace CLI
  (the one people actually use, because its auth UX doesn't hurt)

It does not yet match either of them command for command — see
[Coverage](#coverage-against-the-upstream-tools) for the measured numbers
rather than a promise. What it does take wholesale is `gog`'s philosophy for
authentication: **one command, browser
opens, you approve, done** — with multi-account support, aliases, and
automatic token refresh. Zero runtime dependencies (Python ≥ 3.10 stdlib only).

## Install

```sh
pip install .          # installs the `gsuite` entry point
# or run from a checkout:
python3 -m gsuite.cli --help
```

## Authentication

One-time setup: create a **Desktop app** OAuth client in a Google Cloud
project, download its JSON, then:

```sh
gsuite auth credentials set client_secret.json
gsuite auth login                       # browser opens; email auto-detected
gsuite auth login work@corp.com --services gmail,calendar,drive,admin
gsuite auth alias set work work@corp.com
gsuite -a work gmail search is:unread   # act as a specific account
gsuite auth doctor                      # diagnose setup problems
```

Tokens are stored per account under the config directory (`~/.config/gsuite`
by default, `%APPDATA%\gsuite` on Windows, `$XDG_CONFIG_HOME/gsuite` when set)
in files created mode `0600` inside a `0700` directory, and refreshed
automatically. `gsuite auth logout` revokes the grant at Google rather than
just deleting the local copy. `GSUITE_CLIENT_ID` / `GSUITE_CLIENT_SECRET`
override the stored client; `GSUITE_CONFIG_DIR` relocates all state;
`GSUITE_ACCESS_TOKEN` supplies a token directly.

## Documentation

Full docs live in [`docs/`](docs/index.md) (an MkDocs Material site —
`pip install mkdocs-material && mkdocs serve`, or browse the Markdown right
on GitHub):

- [Architecture](docs/architecture.md) — layer map and sequence diagrams
- [Authentication guide](docs/guides/authentication.md)
- [Scripting & automation](docs/guides/scripting.md)
- [Command reference](docs/reference/index.md) — generated from the CLI's own
  parser tree by `scripts/gen_docs.py`, with options tables and examples
- [Development](docs/development.md) — the red-green workflow

## Commands

Global flags go before the service name: `-a/--account <email|alias>` picks
the account, `--json` and `--csv` switch output shape, `--fields A,B` narrows
the columns, `--readonly` refuses any request that could modify data,
`--debug` traces HTTP metadata to stderr, and `--timeout SECONDS` caps each
request. The table below is generated from the CLI's own parser tree — see
the [command reference](docs/reference/index.md) for options tables and
worked examples.

<!-- BEGIN GENERATED COMMAND SUMMARY -->
| Service | Commands |
| --- | --- |
| [`gsuite auth`](docs/reference/auth.md)<br/><sub>login, accounts, aliases, tokens</sub> | `login` · `logout` · `revoke` · `list` · `status` · `switch` · `alias set|rm|list` · `credentials set` · `token` · `adc` · `doctor` |
| [`gsuite gmail`](docs/reference/gmail.md)<br/><sub>search, read, send, labels, drafts</sub> | `search` · `get` · `thread` · `attachments` · `send` · `reply` · `forward` · `archive` · `unarchive` · `mark-read` · `mark-unread` · `spam` · `unspam` · `trash` · `untrash` · `labels list|create|apply|remove` · `drafts list|create` · `vacation show|set|off` · `signature show|set` · `filters list|create|rm` · `batch-modify` |
| [`gsuite calendar`](docs/reference/calendar.md)<br/><sub>calendars, events, agenda</sub> | `calendars` · `events` · `agenda` · `create` · `get` · `update` · `respond` · `freebusy` · `delete` |
| [`gsuite drive`](docs/reference/drive.md)<br/><sub>files: ls, search, upload, share</sub> | `ls` · `search` · `audit` · `info` · `mv` · `mkdir` · `upload` · `download` · `export` · `share` · `permissions` · `trash` · `restore` · `rm` · `copy` · `drives` |
| [`gsuite docs`](docs/reference/docs.md)<br/><sub>Google Docs: create, cat, append, replace</sub> | `create` · `cat` · `append` · `replace` |
| [`gsuite sheets`](docs/reference/sheets.md)<br/><sub>spreadsheets: read/append/update</sub> | `create` · `read` · `append` · `update` · `clear` · `tabs` · `add-tab` · `rm-tab` |
| [`gsuite slides`](docs/reference/slides.md)<br/><sub>presentations: create, info, cat, add</sub> | `create` · `info` · `cat` · `add` |
| [`gsuite contacts`](docs/reference/contacts.md)<br/><sub>list, search, create contacts</sub> | `list` · `search` · `get` · `create` · `update` · `rm` · `groups list|create|add` |
| [`gsuite tasks`](docs/reference/tasks.md)<br/><sub>task lists and tasks</sub> | `lists` · `list` · `add` · `update` · `move` · `done` · `rm` · `clear-completed` |
| [`gsuite chat`](docs/reference/chat.md)<br/><sub>Google Chat spaces and messages</sub> | `spaces` · `create-space` · `members` · `add-member` · `messages` · `send` · `reply` |
| [`gsuite keep`](docs/reference/keep.md)<br/><sub>Google Keep notes</sub> | `list` · `get` · `create` · `rm` · `share` · `unshare` |
| [`gsuite admin`](docs/reference/admin.md)<br/><sub>Workspace admin: users, groups</sub> | `users list|info|create|update|reset-password|suspend|unsuspend|delete` · `groups list|create|members|add-member|rm-member|delete` · `orgunits` |
| [`gsuite forms`](docs/reference/forms.md)<br/><sub>Google Forms: create, inspect, responses</sub> | `create` · `get` · `questions` · `responses` |
| [`gsuite meet`](docs/reference/meet.md)<br/><sub>Google Meet spaces and conferences</sub> | `create` · `get` · `end` · `conferences` · `participants` |
| [`gsuite searchconsole`](docs/reference/searchconsole.md)<br/><sub>Search Console: sites, search analytics, URL inspection</sub> | `sites` · `query` · `inspect` |
| [`gsuite analytics`](docs/reference/analytics.md)<br/><sub>Google Analytics 4: properties and reports</sub> | `properties` · `report` · `realtime` |
| [`gsuite api`](docs/reference/api.md)<br/><sub>raw calls to any Google API</sub> | `call` · `describe` · `list` |
| [`gsuite completion`](docs/reference/completion.md)<br/><sub>shell tab-completion (generated from the parser tree)</sub> | `bash` · `zsh` |
| [`gsuite workflow`](docs/reference/workflow.md)<br/><sub>cross-service helpers built from several APIs</sub> | `standup-report` · `meeting-prep` · `weekly-digest` · `email-to-task` · `file-announce` |
<!-- END GENERATED COMMAND SUMMARY -->

### Notes

- **`gsuite api`** is the escape hatch: every Google API method is reachable
  even without a hand-crafted command.

  ```sh
  gsuite api list                          # all Google APIs (Discovery directory)
  gsuite api describe gmail                # every method of an API
  gsuite api call GET drive/v3/about --param fields=user
  gsuite api call POST https://forms.googleapis.com/v1/forms --body @form.json
  ```

- **`gsuite completion`** emits tab completion built from the same parser
  tree: `source <(gsuite completion bash)` (or `zsh`).
- **`gsuite keep`** requires a Google Workspace enterprise account — the Keep
  API is not available to consumer accounts.
- **`gsuite admin`** requires a Workspace admin account with the `admin`
  service authorized at login.

## Development

Built strictly red-green, one increment per commit, on a single branch.
The whole quality gate is one deterministic script with terse output:

```sh
python3 scripts/verify.py         # GREEN gate: compile + full test suite
python3 scripts/verify.py --red   # before implementing: proves new tests fail
```

Tests never touch the network: all HTTP funnels through
`gsuite/transport.py`, which tests replace with a programmable fake
(`tests/conftest.py`). `pip install pytest` is the only dev dependency.

## Design notes

- **No runtime dependencies** — urllib, argparse, email, http.server only.
- **One HTTP seam** — `transport.request()` is the single network chokepoint:
  easy to fake, easy to audit.
- **401 self-healing** — API calls force a token refresh and retry once.
- **Errors say what to do** — a scope failure names the service and the exact
  `auth login` command; network failures and closed pipes are ordinary exits.
- **Transient-error backoff** — 429/5xx retried at 1/2/4s, honoring `Retry-After`.
- **Pagination everywhere** — `Client.paged()` follows `nextPageToken`.
- **`--readonly` guard** — enforced at the single client chokepoint, so a
  non-GET is refused before any token or network work happens.
- **Docs can't drift** — the command reference *and* the README table are
  generated from the parser tree; `verify.py` fails if either goes stale.
## Coverage against the upstream tools

This project set out to combine two command surfaces, so how much of them it
actually reaches is measured rather than asserted. `scripts/parity.py` reads
both projects' own published command lists and compares them with this CLI's
parser tree; the table below is generated by it and `verify.py` fails if it
goes stale.

<!-- BEGIN GENERATED PARITY -->

| Upstream tool | Commands | Provided here | Deliberately out of scope | Not yet |
| --- | --- | --- | --- | --- |
| `gws` | 24 | 10 (53% of in-scope) | 5 | 9 |
| `gog` | 586 | 97 (18% of in-scope) | 41 | 448 |

`gsuite` ships **154 commands**. Percentages are of the in-scope surface — the exclusions and their reasons are in [`parity/mapping.tsv`](parity/mapping.tsv), and the upstream lists in [`parity/upstream.tsv`](parity/upstream.tsv) carry the URL and digest they were read from. Regenerate with `python3 scripts/parity.py`.

<!-- END GENERATED PARITY -->

The honest summary: the commands people reach for daily are here, and a long
tail is not. `gws` is the closer match, because its hand-written helper verbs
are exactly the ergonomics this tool was built for — its other surface is
generated from Google's Discovery service at runtime and has no fixed list,
which `gsuite api call` and `gsuite api describe` reach instead. `gog` is a
much larger, older surface: whole services (`classroom`, `appscript`,
`sites`, `groups`) and deep per-service trees (Drive comments and revisions,
Gmail send-as and delegates, the Docs batch-update surface) are not built
yet.

To see exactly what is missing, ask:

```console
$ python3 scripts/parity.py --missing gog | head
```
