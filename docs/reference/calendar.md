# gsuite calendar

Calendars, events, agenda.

```text
usage: gsuite calendar [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite calendar calendars`

List calendars.

```text
usage: gsuite calendar calendars [-h]
```

### `gsuite calendar events`

List events in a time window.

```text
usage: gsuite calendar events [-h] [--calendar CALENDAR] [--from WHEN]
                              [--to TO] [--tz NAME] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--from WHEN` |  |  | RFC3339 or YYYY-MM-DD lower bound |
| `--to TO` |  |  | RFC3339 or YYYY-MM-DD upper bound |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |
| `--max MAX` |  | `50` | maximum results (default: 50) |

### `gsuite calendar agenda`

Events for one day (default: today).

```text
usage: gsuite calendar agenda [-h] [--calendar CALENDAR] [--date DATE]
                              [--tz NAME]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--date DATE` |  |  | YYYY-MM-DD |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |

### `gsuite calendar create`

Create an event.

```text
usage: gsuite calendar create [-h] [--calendar CALENDAR] --summary SUMMARY
                              --start START [--end END]
                              [--attendees ATTENDEES]
                              [--description DESCRIPTION]
                              [--location LOCATION] [--tz NAME]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--summary SUMMARY` | yes |  |  |
| `--start START` | yes |  | YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM |
| `--end END` |  |  |  |
| `--attendees ATTENDEES` |  |  | comma-separated emails |
| `--description DESCRIPTION` |  |  |  |
| `--location LOCATION` |  |  |  |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |

### `gsuite calendar get`

Show one event.

```text
usage: gsuite calendar get [-h] [--calendar CALENDAR] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `id` | yes |  |  |

### `gsuite calendar update`

Update fields of an event.

```text
usage: gsuite calendar update [-h] [--calendar CALENDAR] [--summary SUMMARY]
                              [--start START] [--end END]
                              [--location LOCATION]
                              [--description DESCRIPTION] [--tz NAME]
                              id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `id` | yes |  |  |
| `--summary SUMMARY` |  |  |  |
| `--start START` |  |  | YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM |
| `--end END` |  |  | YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM |
| `--location LOCATION` |  |  |  |
| `--description DESCRIPTION` |  |  |  |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |

### `gsuite calendar respond`

Respond to an event invitation.

```text
usage: gsuite calendar respond [-h] [--calendar CALENDAR] --as
                               {accepted,declined,tentative}
                               id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `id` | yes |  |  |
| `--as {accepted,declined,tentative}` | yes |  | response status |

### `gsuite calendar freebusy`

Busy blocks per calendar in a window.

```text
usage: gsuite calendar freebusy [-h] --from WHEN --to WHEN
                                [--calendars CALENDARS] [--tz NAME]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--from WHEN` | yes |  | RFC3339 or YYYY-MM-DD lower bound |
| `--to WHEN` | yes |  | RFC3339 or YYYY-MM-DD upper bound |
| `--calendars CALENDARS` |  |  | comma-separated calendar ids (default: primary) |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |

### `gsuite calendar delete`

Delete an event.

```text
usage: gsuite calendar delete [-h] [--calendar CALENDAR] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `id` | yes |  |  |

## Examples

**Today's agenda**

```console
$ gsuite calendar agenda
ID     START                 SUMMARY   LOCATION
e1a2   2026-01-05T09:00:00Z  Standup   Zoom
```

**Create a timed event with attendees**

```console
$ gsuite calendar create --summary 'Design review' --start 2026-01-07T14:00 --end 2026-01-07T15:00 --attendees alice@example.com,bob@example.com
created e9f3 https://www.google.com/calendar/event?eid=...
```
