# gsuite calendar

Calendars, events, agenda, conflicts, sharing.

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

### `gsuite calendar search`

Search events by text.

```text
usage: gsuite calendar search [-h] [--calendar CALENDAR] [--from WHEN]
                              [--to WHEN] [--tz NAME] [--max MAX]
                              query
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `query` | yes |  | free text matched against summary, description, location and attendees |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--from WHEN` |  |  | RFC3339 or YYYY-MM-DD lower bound |
| `--to WHEN` |  |  | RFC3339 or YYYY-MM-DD upper bound |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |
| `--max MAX` |  | `50` | maximum results (default: 50) |

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

### `gsuite calendar move`

Move an event to another calendar.

```text
usage: gsuite calendar move [-h] --to CALENDAR [--calendar CALENDAR] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--to CALENDAR` | yes |  | destination calendar id |
| `--calendar CALENDAR` |  | `primary` | calendar the event is on now (default: primary) |

### `gsuite calendar create-calendar`

Create a calendar (not an event).

```text
usage: gsuite calendar create-calendar [-h] --summary SUMMARY
                                       [--description DESCRIPTION] [--tz NAME]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--summary SUMMARY` | yes |  | the calendar's name |
| `--description DESCRIPTION` |  |  |  |
| `--tz NAME` |  |  | IANA timezone the calendar defaults to, e.g. America/New_York |

### `gsuite calendar delete-calendar`

Delete a calendar for everyone.

```text
usage: gsuite calendar delete-calendar [-h] calendar
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `calendar` | yes |  | calendar id |

### `gsuite calendar subscribe`

Add an existing calendar to your calendar list.

```text
usage: gsuite calendar subscribe [-h] [--color ID] calendar
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `calendar` | yes |  | calendar id |
| `--color ID` |  |  | colorId to show it in (see `calendar colors`) |

### `gsuite calendar unsubscribe`

Remove a calendar from your calendar list.

```text
usage: gsuite calendar unsubscribe [-h] calendar
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `calendar` | yes |  | calendar id |

### `gsuite calendar acl`

Manage who a calendar is shared with.

#### `gsuite calendar acl list`

List sharing rules.

```text
usage: gsuite calendar acl list [-h] [--calendar CALENDAR]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |

#### `gsuite calendar acl add`

Share a calendar with someone.

```text
usage: gsuite calendar acl add [-h] --role
                               {none,freeBusyReader,reader,writer,owner}
                               [--type {user,group,domain,default}]
                               [--calendar CALENDAR]
                               [scope]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `scope` |  |  | email address, group address, or domain (omit for --type default) |
| `--role {none,freeBusyReader,reader,writer,owner}` | yes |  | what the grantee may do |
| `--type {user,group,domain,default}` |  | `user` | who the scope names (default: user) |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |

#### `gsuite calendar acl remove`

Revoke a sharing rule.

```text
usage: gsuite calendar acl remove [-h] [--calendar CALENDAR] rule
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `rule` | yes |  | rule id, e.g. user:alice@example.com |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |

### `gsuite calendar colors`

List the available event/calendar colors.

```text
usage: gsuite calendar colors [-h] [--kind {event,calendar}]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--kind {event,calendar}` |  |  | show only one palette (default: both) |

### `gsuite calendar conflicts`

Find overlapping events in a window.

```text
usage: gsuite calendar conflicts [-h] [--calendar CALENDAR] [--from WHEN]
                                 [--to WHEN] [--include-all-day] [--tz NAME]
                                 [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--from WHEN` |  |  | RFC3339 or YYYY-MM-DD lower bound (default: today) |
| `--to WHEN` |  |  | RFC3339 or YYYY-MM-DD upper bound (default: 7 days out) |
| `--include-all-day` |  |  | count all-day events too (holidays and PTO overlap everything, so they are skipped by default) |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |
| `--max MAX` |  | `250` | maximum results (default: 250) |

### `gsuite calendar changed`

Events changed recently, deletions included.

```text
usage: gsuite calendar changed [-h] [--calendar CALENDAR] [--since WHEN]
                               [--tz NAME] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--since WHEN` |  |  | RFC3339 or YYYY-MM-DD lower bound on the last change (default: 7 days ago) |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |
| `--max MAX` |  | `50` | maximum results (default: 50) |

### `gsuite calendar out-of-office`

Block time as out of office.

```text
usage: gsuite calendar out-of-office [-h] [--summary SUMMARY]
                                     [--calendar CALENDAR] --start WHEN --end
                                     WHEN [--decline {all,new,none}]
                                     [--message MESSAGE] [--tz NAME]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--summary SUMMARY` |  | `Out of office` |  |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--start WHEN` | yes |  | YYYY-MM-DDTHH:MM (these blocks are always timed) |
| `--end WHEN` | yes |  | YYYY-MM-DDTHH:MM (these blocks are always timed) |
| `--decline {all,new,none}` |  | `none` | auto-decline conflicting invitations (default: none) |
| `--message MESSAGE` |  |  | text sent with an automatic decline |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |

### `gsuite calendar focus-time`

Block time as focus time.

```text
usage: gsuite calendar focus-time [-h] [--summary SUMMARY]
                                  [--calendar CALENDAR] --start WHEN --end
                                  WHEN [--decline {all,new,none}]
                                  [--message MESSAGE] [--tz NAME]
                                  [--chat {available,doNotDisturb}]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--summary SUMMARY` |  | `Focus time` |  |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--start WHEN` | yes |  | YYYY-MM-DDTHH:MM (these blocks are always timed) |
| `--end WHEN` | yes |  | YYYY-MM-DDTHH:MM (these blocks are always timed) |
| `--decline {all,new,none}` |  | `none` | auto-decline conflicting invitations (default: none) |
| `--message MESSAGE` |  |  | text sent with an automatic decline |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |
| `--chat {available,doNotDisturb}` |  |  | chat status while the block is on |

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

**Find this week's double-bookings**

```console
$ gsuite calendar conflicts
FROM                  TO                    EVENT    ID    CONFLICTS-WITH  WITH-ID
2026-01-05T09:15:00Z  2026-01-05T09:30:00Z  Standup  e1a2  Design review   e9f3
```

**Block a week off, declining new invitations as they arrive**

```console
$ gsuite calendar out-of-office --start 2026-01-12T09:00 --end 2026-01-16T17:00 --decline new --message 'Back on the 19th'
created ooo7 https://www.google.com/calendar/event?eid=...
```

**Share a calendar, then check who can see it**

```console
$ gsuite calendar acl add alice@example.com --role writer
$ gsuite calendar acl list
ID                   ROLE    TYPE  WHO
user:alice@example.com  writer  user  alice@example.com
```
