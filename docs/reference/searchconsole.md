# gsuite searchconsole

Search Console: sites, search analytics, URL inspection.

```text
usage: gsuite searchconsole [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`.

## Commands

### `gsuite searchconsole sites`

List verified sites.

```text
usage: gsuite searchconsole sites [-h]
```

### `gsuite searchconsole query`

Query search analytics for a site.

```text
usage: gsuite searchconsole query [-h] --from DATE --to DATE
                                  [--dimensions DIMENSIONS] [--max MAX]
                                  site
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `site` | yes |  | e.g. https://example.com/ or sc-domain:example.com |
| `--from DATE` | yes |  | start date, YYYY-MM-DD |
| `--to DATE` | yes |  | end date, YYYY-MM-DD |
| `--dimensions DIMENSIONS` |  |  | comma-separated, e.g. query,page,country,device |
| `--max MAX` |  | `25` | maximum results (default: 25) |

### `gsuite searchconsole inspect`

Inspect a URL's index status.

```text
usage: gsuite searchconsole inspect [-h] site url
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `site` | yes |  | the verified site the URL belongs to |
| `url` | yes |  | the full URL to inspect |

## Examples

**Top queries for a site last month**

```console
$ gsuite searchconsole query https://example.com/ --from 2026-01-01 --to 2026-01-31 --dimensions query --max 3
KEYS            CLICKS  IMPRESSIONS  CTR    POSITION
gsuite cli      120     3400         0.035  4.2
```

**Why isn't this page indexed?**

```console
$ gsuite searchconsole inspect https://example.com/ https://example.com/new-post
verdict: PASS
coverage: Submitted and indexed
lastCrawl: 2026-01-05T10:00:00Z
robots: ALLOWED
```
