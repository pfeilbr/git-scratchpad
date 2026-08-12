# Authentication

`gsuite` uses the OAuth 2.0 *installed app* flow with a loopback redirect:
`gsuite auth login` opens your browser, you approve, and the CLI catches the
redirect on `127.0.0.1` — no copying codes around. Tokens refresh themselves.

## One-time setup: an OAuth client

Google requires every installed app to bring its own OAuth client.

1. Open the [Google Cloud console](https://console.cloud.google.com/) and
   create (or pick) a project.
2. Enable the APIs you plan to use (Gmail API, Calendar API, Drive API, …).
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**,
   application type **Desktop app**. Download the JSON.
4. Hand it to gsuite:

```console
$ gsuite auth credentials set client_secret_1234.json
OAuth client credentials saved
```

The file may be the raw `{"client_id": …}` form or the console's
`{"installed": {…}}` / `{"web": {…}}` wrapper — all three are accepted.
Alternatively, skip the stored file entirely and export
`GSUITE_CLIENT_ID` / `GSUITE_CLIENT_SECRET`.

## Logging in

```console
$ gsuite auth login
Opening browser for Google sign-in…
Logged in as you@example.com (services: calendar, contacts, drive, gmail)
```

- The email is auto-detected from the token; pass it explicitly to be safe
  in multi-profile browsers: `gsuite auth login you@example.com`.
- Scope only what you need with `--services`
  (`gmail,calendar,drive,docs,sheets,slides,contacts,tasks,chat,keep,admin`).
  Fewer scopes → a shorter consent screen and safer tokens.
- Tokens land in `~/.config/gsuite/tokens/<email>.json` with mode `0600`
  and are refreshed automatically (60 s before expiry, plus a self-healing
  retry on 401).

## Multiple accounts

```console
$ gsuite auth login work@corp.com --services gmail,calendar,admin
$ gsuite auth login me@gmail.com
$ gsuite auth alias set work work@corp.com
$ gsuite auth list
* me@gmail.com  token:valid  services:calendar,contacts,drive,gmail
  work@corp.com  token:valid  services:admin,calendar,gmail
$ gsuite -a work gmail search in:inbox   # one-off routing
$ gsuite auth switch work@corp.com       # change the default
```

`-a/--account` accepts an email **or an alias** and goes before the service
name. `auth logout <email>` removes the account, its token, and any aliases.

## Headless / CI machines

1. Log in once on a machine with a browser.
2. Copy `~/.config/gsuite/` to the headless host (or set
   `GSUITE_CONFIG_DIR` to a mounted secret path).
3. Refresh happens over HTTPS without any browser.

For other tooling, `gsuite auth token` prints a fresh access token — see
[Scripting & automation](scripting.md).

## Troubleshooting

`gsuite auth doctor` checks the whole chain and exits non-zero on failure:

```console
$ gsuite auth doctor
OK   OAuth client configured
FAIL at least one account — run `gsuite auth login <email>`
```

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `no OAuth client configured` | no client.json / env vars | `gsuite auth credentials set …` |
| browser opens, then `access_denied` | consent declined, or the OAuth app is in *Testing* and you're not a test user | add yourself as a test user in the console |
| `token has no refresh_token` | client re-used an old consent | `gsuite auth login` again (we always request `prompt=consent`) |
| `HTTP 403 … accessNotConfigured` | API not enabled in your GCP project | enable it in **APIs & Services** |
| `HTTP 401` loops | token revoked | `gsuite auth login <email>` |
