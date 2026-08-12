# gsuite tasks

Task lists and tasks.

```text
usage: gsuite tasks [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite tasks lists`

List task lists.

```text
usage: gsuite tasks lists [-h]
```

### `gsuite tasks list`

List tasks.

```text
usage: gsuite tasks list [-h] [--list LIST] [--all] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--list LIST` |  | `@default` | task list id (default: @default) |
| `--all` |  |  | include completed |
| `--max MAX` |  | `100` | maximum results (default: 100) |

### `gsuite tasks add`

Add a task.

```text
usage: gsuite tasks add [-h] [--list LIST] [--due DUE] [--notes NOTES] title
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `title` | yes |  |  |
| `--list LIST` |  | `@default` | task list id (default: @default) |
| `--due DUE` |  |  | YYYY-MM-DD or RFC3339 |
| `--notes NOTES` |  |  |  |

### `gsuite tasks done`

Mark a task completed.

```text
usage: gsuite tasks done [-h] [--list LIST] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--list LIST` |  | `@default` | task list id (default: @default) |

### `gsuite tasks rm`

Delete a task.

```text
usage: gsuite tasks rm [-h] [--list LIST] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--list LIST` |  | `@default` | task list id (default: @default) |

## Examples

**Add a task with a due date and complete it**

```console
$ gsuite tasks add 'File expenses' --due 2026-01-09
$ gsuite tasks done t1
completed t1
```
