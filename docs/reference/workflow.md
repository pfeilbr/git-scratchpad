# gsuite workflow

Cross-service helpers built from several APIs.

```text
usage: gsuite workflow [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite workflow standup-report`

Today's meetings and open tasks, as one list.

```text
usage: gsuite workflow standup-report [-h] [--calendar CALENDAR] [--date DATE]
                                      [--tz NAME] [--list LIST]
                                      [--max-tasks N]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--date DATE` |  |  | YYYY-MM-DD |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |
| `--list LIST` |  | `@default` | task list id (default: @default) |
| `--max-tasks N` |  | `25` | maximum open tasks to include (default: 25) |

### `gsuite workflow meeting-prep`

Brief for your next meeting: agenda, attendees, linked files.

```text
usage: gsuite workflow meeting-prep [-h] [--calendar CALENDAR] [--tz NAME]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |

### `gsuite workflow weekly-digest`

This week's meetings and the unread-mail count.

```text
usage: gsuite workflow weekly-digest [-h] [--calendar CALENDAR] [--date DATE]
                                     [--tz NAME]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--calendar CALENDAR` |  | `primary` | calendar id (default: primary) |
| `--date DATE` |  |  | YYYY-MM-DD — any day in the week (default: today) |
| `--tz NAME` |  |  | IANA timezone for bare dates and times, e.g. America/New_York (default: the system timezone) |

### `gsuite workflow email-to-task`

Turn a Gmail message into a task that links back to it.

```text
usage: gsuite workflow email-to-task [-h] [--list LIST] [--title TITLE]
                                     [--due DUE]
                                     id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  | Gmail message id |
| `--list LIST` |  | `@default` | task list id (default: @default) |
| `--title TITLE` |  |  | task title (default: the mail's subject) |
| `--due DUE` |  |  | YYYY-MM-DD or RFC3339 |

### `gsuite workflow file-announce`

Post a Drive file's name and link to a Chat space.

```text
usage: gsuite workflow file-announce [-h] --space SPACE [--text TEXT] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  | Drive file id |
| `--space SPACE` | yes |  | e.g. spaces/AAAA |
| `--text TEXT` |  |  | a note to put above the link |

## Examples

**What does today look like? (Calendar + Tasks)**

```console
$ gsuite workflow standup-report
KIND     WHEN                       ITEM
meeting  2026-01-05T09:00:00-05:00  Standup
meeting  2026-01-05T14:00:00-05:00  Design review
task     2026-01-09T00:00:00Z       File expenses
```

**Walk into the next meeting prepared (Calendar + Drive)**

```console
$ gsuite workflow meeting-prep
summary: Design review
start: 2026-01-07T14:00:00-05:00
end: 2026-01-07T15:00:00-05:00
location: Room 4
attendees: Ada Lovelace (accepted), bob@example.com (needsAction)
files: Q1 budget (https://docs.google.com/spreadsheets/d/…)
agenda: Decide the launch date.
```

**The week at a glance (Calendar + Gmail)**

```console
$ gsuite workflow weekly-digest
from: 2026-01-05
to: 2026-01-11
meetings: 7
days: 2026-01-05 (3), 2026-01-07 (4)
unread: 12
```

**File a mail as work to do (Gmail + Tasks)**

```console
$ gsuite workflow email-to-task 19ab3f --due 2026-01-09
added t9 Q1 roadmap
```

**Tell the team about a file (Drive + Chat)**

```console
$ gsuite workflow file-announce 1AbCdEf --space spaces/AAAA --text 'Numbers are final'
sent spaces/AAAA/messages/BBBB.CCCC
```
