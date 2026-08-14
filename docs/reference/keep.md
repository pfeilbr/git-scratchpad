# gsuite keep

Google Keep notes.

```text
usage: gsuite keep [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite keep list`

List notes.

```text
usage: gsuite keep list [-h] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--max MAX` |  | `50` | maximum results (default: 50) |

### `gsuite keep get`

Show a note.

```text
usage: gsuite keep get [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite keep create`

Create a text note.

```text
usage: gsuite keep create [-h] [--title TITLE] --text TEXT
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--title TITLE` |  |  |  |
| `--text TEXT` | yes |  |  |

### `gsuite keep rm`

Delete a note.

```text
usage: gsuite keep rm [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite keep share`

Grant an email write access to a note.

```text
usage: gsuite keep share [-h] id email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `email` | yes |  |  |

### `gsuite keep unshare`

Revoke an email's access to a note.

```text
usage: gsuite keep unshare [-h] id email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `email` | yes |  |  |

## Examples

**Capture a note**

```console
$ gsuite keep create --title Ideas --text 'One CLI for everything'
created notes/n123
```
