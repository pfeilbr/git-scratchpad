# gsuite meet

Google Meet spaces and conferences.

```text
usage: gsuite meet [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite meet create`

Create a meeting space.

```text
usage: gsuite meet create [-h] [--access {OPEN,TRUSTED,RESTRICTED}]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--access {OPEN,TRUSTED,RESTRICTED}` |  |  | who can join without knocking |

### `gsuite meet get`

Show a meeting space.

```text
usage: gsuite meet get [-h] space
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `space` | yes |  | e.g. spaces/abc or abc |

### `gsuite meet end`

End the active conference in a space.

```text
usage: gsuite meet end [-h] space
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `space` | yes |  | e.g. spaces/abc or abc |

### `gsuite meet conferences`

List past/ongoing conference records.

```text
usage: gsuite meet conferences [-h] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--max MAX` |  | `25` | maximum results (default: 25) |

### `gsuite meet participants`

List participants of a conference record.

```text
usage: gsuite meet participants [-h] [--max MAX] record
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `record` | yes |  | e.g. conferenceRecords/abc or abc |
| `--max MAX` |  | `50` | maximum results (default: 50) |

## Examples

**Create a space and share the link**

```console
$ gsuite meet create --access TRUSTED
created spaces/abc-defg-hij https://meet.google.com/abc-defg-hij
```

**Who attended the last conference?**

```console
$ gsuite meet conferences --max 1
$ gsuite meet participants conferenceRecords/c1
NAME                                 USER           JOINED
conferenceRecords/c1/participants/p1 Ada Lovelace   2026-01-05T10:00:00Z
```
