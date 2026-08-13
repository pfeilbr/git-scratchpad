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
`https://www.googleapis.com/`.

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
