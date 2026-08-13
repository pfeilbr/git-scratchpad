# gsuite-cli

One command-line tool for all of Google Workspace — Gmail, Calendar, Drive,
Docs, Sheets, Slides, Contacts, Tasks, Chat, Keep, and Workspace Admin —
plus a raw passthrough to **any** Google API via the Discovery service.

It combines the command surfaces of two existing tools:

- [`gws`](https://github.com/googleworkspace/cli) — Google's official
  Workspace CLI (dynamic Discovery-driven coverage, admin, generic API calls)
- [`gog`](https://github.com/openclaw/gogcli) — steipete's Workspace CLI
  (the one people actually use, because its auth UX doesn't hurt)

…and keeps `gog`'s philosophy for authentication: **one command, browser
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

Tokens are stored per account under `~/.config/gsuite/tokens/` (mode 0600)
and refreshed automatically. `GSUITE_CLIENT_ID` / `GSUITE_CLIENT_SECRET`
override the stored client; `GSUITE_CONFIG_DIR` relocates all state.

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

Global flags (before the service name): `-a/--account <email|alias>`,
`--json` for machine-readable output. The summary below is the short
version; see the [command reference](docs/reference/index.md) for options
tables and worked examples.

### `gsuite auth`
`login [email] [--services a,b]` · `logout <email>` · `list` · `status` ·
`switch <email>` · `alias set|rm|list` · `credentials set <file>` ·
`token` (print a fresh access token for scripts) · `doctor`

### `gsuite gmail`
`search <query> [--max N]` · `get <id>` · `send --to --subject --body [--cc --bcc]` ·
`reply <id> --body` · `forward <id> --to` · `trash <id>` ·
`labels list|create|apply|remove` · `drafts list|create`

### `gsuite calendar`
`calendars` · `events [--from --to --max --calendar]` · `agenda [--date]` ·
`create --summary --start [--end --attendees --location --description]` ·
`get <id>` · `delete <id>`

### `gsuite drive`
`ls [folder]` · `search <query>` · `upload <file> [--parent --name --mime]` ·
`download <id> [-o]` · `export <id> --mime [-o]` · `mkdir <name> [--parent]` ·
`share <id> --with <email|anyone> [--role]` · `permissions <id>` ·
`copy <id> [--name]` · `rm <id>` · `audit` (find link-/publicly-shared files)

### `gsuite docs`
`create --title` · `cat <id>` · `append <id> --text`

### `gsuite sheets`
`create --title` · `read <id> <range>` · `append <id> <range> --values "a,b;c,d"` ·
`update <id> <range> --values` · `clear <id> <range>`

### `gsuite slides`
`create --title` · `info <id>`

### `gsuite contacts`
`list [--max]` · `search <query>` · `create --name [--email --phone]` · `rm <resource>`

### `gsuite tasks`
`lists` · `list [--list --all --max]` · `add <title> [--due --notes]` ·
`done <id>` · `rm <id>`

### `gsuite chat`
`spaces` · `messages <space> [--max]` · `send <space> --text`

### `gsuite keep`
`list` · `get <id>` · `create [--title] --text`
(Note: the Keep API is only available to Google Workspace enterprise accounts.)

### `gsuite admin`
`users list|info|create|suspend|unsuspend|delete` ·
`groups list|create|members|add-member`
(Requires a Workspace admin account with the `admin` service authorized.)

### `gsuite forms`
`create --title` · `get <id>` · `questions <id>` · `responses <id> [--max]`

### `gsuite meet`
`create [--access]` · `get <space>` · `end <space>` · `conferences [--max]` ·
`participants <record> [--max]`

### `gsuite api`
The escape hatch — every Google API method is reachable even without a
hand-crafted command:

```sh
gsuite api list                          # all Google APIs (Discovery directory)
gsuite api describe gmail                # every method of an API
gsuite api call GET drive/v3/about --param fields=user
gsuite api call POST https://forms.googleapis.com/v1/forms --body '{"info":{"title":"F"}}'
```

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
- **Pagination everywhere** — `Client.paged()` follows `nextPageToken`.
- Not yet covered from the upstream tools: gog's analytics/searchconsole/
  youtube/zoom integrations and gws's AI "+workflow" helpers; `gsuite api call`
  reaches those APIs in the meantime.
