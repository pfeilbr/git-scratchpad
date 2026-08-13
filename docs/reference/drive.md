# gsuite drive

Files: ls, search, upload, share.

```text
usage: gsuite drive [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite drive ls`

List a folder (default: root).

```text
usage: gsuite drive ls [-h] [--max MAX] [folder]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `folder` |  | `root` |  |
| `--max MAX` |  | `100` | maximum results (default: 100) |

### `gsuite drive search`

Search by name or raw Drive query.

```text
usage: gsuite drive search [-h] [--max MAX] query
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `query` | yes |  |  |
| `--max MAX` |  | `50` | maximum results (default: 50) |

### `gsuite drive audit`

Find link-/publicly-shared files.

```text
usage: gsuite drive audit [-h] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--max MAX` |  | `100` | maximum results (default: 100) |

### `gsuite drive info`

Show a file's metadata.

```text
usage: gsuite drive info [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite drive mv`

Move and/or rename a file.

```text
usage: gsuite drive mv [-h] [--parent PARENT] [--name NAME] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--parent PARENT` |  |  | new parent folder id |
| `--name NAME` |  |  | new file name |

### `gsuite drive mkdir`

Create a folder.

```text
usage: gsuite drive mkdir [-h] [--parent PARENT] name
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | yes |  |  |
| `--parent PARENT` |  |  |  |

### `gsuite drive upload`

Upload a local file.

```text
usage: gsuite drive upload [-h] [--parent PARENT] [--name NAME] [--mime MIME]
                           file
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `--parent PARENT` |  |  |  |
| `--name NAME` |  |  | name in Drive (default: local basename) |
| `--mime MIME` |  |  |  |

### `gsuite drive download`

Download file content.

```text
usage: gsuite drive download [-h] [-o OUTPUT] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `-o OUTPUT, --output OUTPUT` |  |  | output path (default: stdout) |

### `gsuite drive export`

Export a Google Doc/Sheet/Slides file.

```text
usage: gsuite drive export [-h] --mime MIME [-o OUTPUT] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--mime MIME` | yes |  | target MIME type, e.g. application/pdf |
| `-o OUTPUT, --output OUTPUT` |  |  | output path (default: stdout) |

### `gsuite drive share`

Grant access to a file.

```text
usage: gsuite drive share [-h] --with EMAIL|anyone
                          [--role {reader,commenter,writer,organizer,fileOrganizer,owner}]
                          id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--with EMAIL|anyone` | yes |  |  |
| `--role {reader,commenter,writer,organizer,fileOrganizer,owner}` |  | `reader` |  |

### `gsuite drive permissions`

List a file's permissions.

```text
usage: gsuite drive permissions [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite drive trash`

Move a file to the trash.

```text
usage: gsuite drive trash [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite drive restore`

Restore a file from the trash.

```text
usage: gsuite drive restore [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite drive rm`

Delete a file permanently.

```text
usage: gsuite drive rm [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite drive copy`

Copy a file.

```text
usage: gsuite drive copy [-h] [--name NAME] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--name NAME` |  |  |  |

## Examples

**List a folder and upload into it**

```console
$ gsuite drive ls
$ gsuite drive upload report.pdf --parent 1AbCdEf
uploaded 1XyZ9 report.pdf
```

**Export a Google Doc as PDF**

```console
$ gsuite drive export 1DocId --mime application/pdf -o notes.pdf
wrote 24576 bytes to notes.pdf
```

**Audit link-shared files**

```console
$ gsuite drive audit
ID     NAME        TYPE       MODIFIED              SIZE  LINK
1XyZ9  budget.xlsx submitted  2026-01-04T12:00:00Z  9812  https://…
```
