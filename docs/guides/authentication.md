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
- Tokens land in `tokens/<email>.json` under the config directory
  (`~/.config/gsuite` by default) with mode `0600`
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
2. Copy the config directory to the headless host (or set
   `GSUITE_CONFIG_DIR` to a mounted secret path — it overrides the location on
   every platform, and wins over `XDG_CONFIG_HOME` and `%APPDATA%`).
3. Refresh happens over HTTPS without any browser.

For other tooling, `gsuite auth token` prints a fresh access token — see
[Scripting & automation](scripting.md).

## Other credential sources

`gsuite auth login` is the happy path, but two other sources work anywhere a
command needs a bearer token — useful in CI, containers, and shared shells.

### A direct access token

Set `GSUITE_ACCESS_TOKEN` and gsuite uses it verbatim: no store lookup, no
refresh, and **no configured account required**.

```console
$ export GSUITE_ACCESS_TOKEN=$(gcloud auth print-access-token)
$ gsuite drive ls          # works on a machine that never ran `auth login`
```

The token is used exactly as given, so it must already carry the scopes the
command needs, and gsuite cannot renew it when it expires (typically one
hour). It wins over every other source, which also makes it the quickest way
to test a token by hand.

### Application Default Credentials

When no stored token is available, gsuite falls back to ADC — the same file
`gcloud auth application-default login` writes:

```console
$ gcloud auth application-default login
$ gsuite auth adc
path: /home/you/.config/gcloud/application_default_credentials.json
exists: yes
type: authorized_user
usable: yes
```

- The location is `$GOOGLE_APPLICATION_CREDENTIALS` if set, otherwise
  `~/.config/gcloud/application_default_credentials.json`.
- `gsuite auth adc` exits `0` when the file is usable and `1` when it is
  missing or unusable, so it drops straight into a shell `if`.
- The minted access token is cached under the current account, exactly like a
  token from `auth login`.

**Service-account keys are not supported.** Authenticating with one means
signing a JWT assertion with RS256, and gsuite is deliberately
zero-dependency (Python stdlib only, no `cryptography`). Pointing ADC at a
`"type": "service_account"` file therefore fails with a clear message rather
than a traceback — use `gsuite auth login`, or mint a token elsewhere and
export it as `GSUITE_ACCESS_TOKEN`.

Resolution order for every API call:

1. `$GSUITE_ACCESS_TOKEN`
2. the account's stored token (refreshed automatically when stale)
3. Application Default Credentials

`gsuite auth doctor` prints the source in effect:

```console
$ gsuite auth doctor
OK   credential source: ADC (/home/you/.config/gcloud/application_default_credentials.json)
```

### Authorizing everything at once

`--services all` expands to every service gsuite knows about — one consent
screen, one token that covers the whole CLI:

```console
$ gsuite auth login --services all
Logged in as you@example.com (services: admin, calendar, chat, contacts, docs, drive, forms, gmail, keep, meet, sheets, slides, tasks)
```

Convenient for a personal machine; prefer an explicit list for shared or
production credentials.

## When a command fails

API errors keep Google's own wording and add the next step, so you rarely have
to guess which of the services needs attention:

```console
$ gsuite gmail search in:inbox
error: HTTP 403: Request had insufficient authentication scopes. — this token is missing the scopes for that call; re-authorize with `gsuite auth login you@example.com --services gmail`
$ gsuite auth login you@example.com --services gmail
```

The service in the suggestion comes from the API the failed call went to, and
the account is the one that made it. Similar advice is added for a `403`
naming an API that is not enabled in your Cloud project, for `429` (quota —
already retried with backoff), and for `401` (credentials rejected — log in
again). Every other error is passed through untouched.

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
| `is a service_account key` | ADC points at a service-account JSON | `gsuite auth login`, or export `GSUITE_ACCESS_TOKEN` |
