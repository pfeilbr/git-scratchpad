# gsuite docs

Google Docs: create, cat, append.

```text
usage: gsuite docs [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite docs create`

Create a document.

```text
usage: gsuite docs create [-h] --title TITLE
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--title TITLE` | yes |  |  |

### `gsuite docs cat`

Print a document's plain text.

```text
usage: gsuite docs cat [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite docs append`

Append text to a document.

```text
usage: gsuite docs append [-h] --text TEXT id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--text TEXT` | yes |  |  |

## Examples

**Create, append, read back**

```console
$ gsuite docs create --title 'Meeting notes'
$ gsuite docs append 1DocId --text 'Decisions: ship it.'
$ gsuite docs cat 1DocId
Decisions: ship it.
```
