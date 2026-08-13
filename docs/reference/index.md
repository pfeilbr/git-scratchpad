# Command reference

One page per service, generated from the CLI's own parser tree by
`scripts/gen_docs.py` (never edit these pages by hand — the
`verify.py` gate fails if they drift from the code).

| Service | Description |
| --- | --- |
| [`gsuite auth`](auth.md) | login, accounts, aliases, tokens |
| [`gsuite gmail`](gmail.md) | search, read, send, labels, drafts |
| [`gsuite calendar`](calendar.md) | calendars, events, agenda |
| [`gsuite drive`](drive.md) | files: ls, search, upload, share |
| [`gsuite docs`](docs.md) | Google Docs: create, cat, append, replace |
| [`gsuite sheets`](sheets.md) | spreadsheets: read/append/update |
| [`gsuite slides`](slides.md) | presentations: create, info, cat, add |
| [`gsuite contacts`](contacts.md) | list, search, create contacts |
| [`gsuite tasks`](tasks.md) | task lists and tasks |
| [`gsuite chat`](chat.md) | Google Chat spaces and messages |
| [`gsuite keep`](keep.md) | Google Keep notes |
| [`gsuite admin`](admin.md) | Workspace admin: users, groups |
| [`gsuite api`](api.md) | raw calls to any Google API |
