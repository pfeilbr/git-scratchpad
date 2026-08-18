# Scripting & automation

Every command is built to compose: stable exit codes, `--json` everywhere,
and two escape hatches (`auth token`, `api call`) for anything the CLI
doesn't wrap yet.

## Machine-readable output

`--json` (before the service name) switches any listing/object command from
aligned tables to JSON:

```console
$ gsuite --json gmail search is:unread --max 2 | jq -r '.[].subject'
Q1 roadmap
Lunch?
```

```sh
# every calendar attendee today, deduplicated
gsuite --json calendar agenda \
  | jq -r '.[].attendees[]?.email' | sort -u
```

## Picking columns with `--fields`

`--fields` narrows any listing to the columns you name, in the order you
name them. Names match the table headers case-insensitively:

```console
$ gsuite --fields name,id gmail labels list
NAME    ID
INBOX   L1
todo    L2
```

An unknown name fails with exit 1 and lists what that command does offer:

```console
$ gsuite --fields nope gmail labels list
error: unknown field: nope (valid fields: ID, NAME, TYPE)
```

It composes with `--json`, where each row shrinks to the same columns keyed
by the lowercased header:

```sh
gsuite --json --fields id,name gmail labels list | jq -r '.[] | .id'
```

## CSV for spreadsheets

`--csv` emits RFC 4180 CSV with a header row instead of the aligned table —
values containing commas or quotes are quoted for you:

```console
$ gsuite --csv --fields name,type gmail labels list
NAME,TYPE
INBOX,system
todo,user
```

`--csv` and `--json` are two different shapes for the same data, so asking
for both is an error (`--json and --csv are mutually exclusive`, exit 1).

## Tracing HTTP with `--debug`

`--debug` traces every API call at the single transport chokepoint, one line
out and one line back, on **stderr** — so it never pollutes a `--json` or
`--csv` pipeline:

```console
$ gsuite --debug --json gmail labels list > labels.json
→ GET https://gmail.googleapis.com/gmail/v1/users/me/labels
← 200 431 bytes
```

The trace is metadata only: no request or response bodies, and no headers
(your bearer token lives in one), so `2> trace.log` is safe to keep.

## Network failures and `--timeout`

A request that never reaches Google — no connectivity, DNS failure,
connection refused, a TLS problem — is an ordinary operational error, not a
crash: one `error:` line on stderr and exit 1, safe to test for in a script.

```console
$ gsuite api call GET https://nonexistent.invalid/x
error: cannot reach nonexistent.invalid: [Errno -2] Name or service not known
```

`--timeout SECONDS` (before the service name) caps how long each HTTP request
may take; it defaults to 30 seconds, and `GSUITE_TIMEOUT` sets the same limit
for a whole session (the flag wins where both are given). Exceeding it says
so explicitly, so a wedged cron job fails fast instead of hanging:

```console
$ gsuite --timeout 5 drive ls
error: timed out after 5s talking to www.googleapis.com (raise the limit with --timeout SECONDS)
```

Invalid values (non-numeric, zero or negative) are rejected before anything
is sent, with the same exit 1.

## Retries: writes are never replayed on a server error

A `429` (rate limited) is retried up to three times with backoff — for every
command — because Google rejects such a request before running any of it, so
resending it cannot do anything twice.

A `5xx` (500, 502, 503, 504) is treated differently, because it does not say
whether the work happened: the request may have been applied and only the
reply lost on the way back. Reads and idempotent writes (`GET`, `PUT`,
`DELETE`) are still retried, but a `POST` or `PATCH` — sending mail, creating
an event, adding a group member — fails immediately with exit 1 rather than
risk a duplicate, and says so:

```console
$ gsuite gmail send --to you@x.com --subject hi --body hi
error: HTTP 503: Backend Error — the request was not retried because replaying a POST could duplicate the operation; it may or may not have been applied, so check before sending it again
```

So a script must not blindly re-run a failed write: check whether it took
effect first (the message may already be in `SENT`, the event already on the
calendar). Retry loops around `gsuite` are safe for reads, not for writes.

## Read-only runs

`--readonly` (before the service name) refuses anything that could modify
data — the check sits at the single client chokepoint, so a non-GET never
reaches the network:

```console
$ gsuite --readonly drive rm 1XyZ9
error: readonly mode: refusing DELETE https://www.googleapis.com/drive/v3/files/1XyZ9
```

Wrap audit scripts and cron jobs in it: a mistaken verb fails loudly with
exit 1 instead of deleting something.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | operational error (`error: …` on stderr — auth, API, bad input) |
| 2 | usage error (unknown command/flags; argparse help shown) |
| 130 | interrupted (Ctrl-C) |

## Access tokens for other tools

`gsuite auth token` prints a fresh (auto-refreshed) bearer token, which makes
`curl` a first-class citizen:

```sh
curl -s -H "Authorization: Bearer $(gsuite auth token)" \
  "https://www.googleapis.com/drive/v3/about?fields=storageQuota" | jq .
```

## Calling APIs without a dedicated command

[`gsuite api`](../reference/api.md) reaches every Google API method:

```sh
gsuite api list                              # what exists (Discovery directory)
gsuite api describe forms                    # methods of one API
gsuite api call GET gmail/v1/users/me/profile
gsuite api call POST https://forms.googleapis.com/v1/forms \
  --body '{"info": {"title": "Feedback"}}'
```

`--param k=v` adds query parameters; a bare path is resolved against
`https://www.googleapis.com/`. Repeat the flag for more parameters — and
repeat the *same key* for APIs that take one parameter several times, such
as Gmail's `metadataHeaders`/`labelIds` or Calendar's `eventTypes`:

```sh
gsuite api call GET gmail/v1/users/me/messages/MSG_ID \
  --param format=metadata \
  --param metadataHeaders=From --param metadataHeaders=Subject
```

A JSON reply is pretty-printed; a reply that isn't JSON (Drive's `export`,
`alt=media`, an HTML error page from a proxy) is printed as text, so it
pipes straight to a file. A truncated or malformed JSON reply is an
`error:` line and exit 1 rather than garbage on stdout.

## Recipes

```sh
# nightly: file yesterday's unread newsletters under a label
for id in $(gsuite --json gmail search 'is:unread category:promotions' \
              | jq -r '.[].id'); do
  gsuite gmail labels apply "$id" newsletter-backlog
done

# weekly Drive hygiene: fail CI if anything is link-shared
test -z "$(gsuite --json drive audit | jq -r '.[].id')"

# provision a starter with one script
gsuite admin users create --email "$1" --first "$2" --last "$3" \
  --password "$(openssl rand -base64 18)"
gsuite admin groups add-member all@corp.com "$1"
```

!!! tip "Isolated state for CI"
    Set `GSUITE_CONFIG_DIR=/path/to/secret` to keep credentials out of the
    default home-directory location — handy for containers and cron.
