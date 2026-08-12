# gsuite keep

Google Keep notes.

```text
usage: gsuite keep [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

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

## Examples

**Capture a note**

```console
$ gsuite keep create --title Ideas --text 'One CLI for everything'
created notes/n123
```
