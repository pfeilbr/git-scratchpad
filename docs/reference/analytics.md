# gsuite analytics

Google Analytics 4: properties and reports.

```text
usage: gsuite analytics [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`.

## Commands

### `gsuite analytics properties`

List GA4 properties.

```text
usage: gsuite analytics properties [-h]
```

### `gsuite analytics report`

Run a GA4 report over a date range.

```text
usage: gsuite analytics report [-h] --from DATE --to DATE [--metrics METRICS]
                               [--dimensions DIMENSIONS] [--max MAX]
                               property
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `property` | yes |  | e.g. properties/123 or 123 |
| `--from DATE` | yes |  | start date, YYYY-MM-DD (or e.g. 28daysAgo) |
| `--to DATE` | yes |  | end date, YYYY-MM-DD (or e.g. today) |
| `--metrics METRICS` |  | `activeUsers` | comma-separated GA4 metric names |
| `--dimensions DIMENSIONS` |  |  | comma-separated GA4 dimension names |
| `--max MAX` |  | `25` | maximum results (default: 25) |

### `gsuite analytics realtime`

Run a GA4 realtime report.

```text
usage: gsuite analytics realtime [-h] [--metrics METRICS]
                                 [--dimensions DIMENSIONS] [--max MAX]
                                 property
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `property` | yes |  | e.g. properties/123 or 123 |
| `--metrics METRICS` |  | `activeUsers` | comma-separated GA4 metric names |
| `--dimensions DIMENSIONS` |  |  | comma-separated GA4 dimension names |
| `--max MAX` |  | `25` | maximum results (default: 25) |

## Examples

**Traffic by country over a date range**

```console
$ gsuite analytics report properties/123 --from 2026-01-01 --to 2026-01-31 --metrics activeUsers,sessions --dimensions country
COUNTRY        ACTIVEUSERS  SESSIONS
United States  412          530
```

**Who's on the site right now?**

```console
$ gsuite analytics properties
$ gsuite analytics realtime 123 --dimensions country
COUNTRY  ACTIVEUSERS
Japan    5
```
