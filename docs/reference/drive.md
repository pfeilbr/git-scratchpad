# gsuite drive

Files: ls, search, upload, share.

```text
usage: gsuite drive [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite drive ls`

List a folder (default: root).

```text
usage: gsuite drive ls [-h] [--drive DRIVE] [--max MAX] [folder]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `folder` |  | `root` |  |
| `--drive DRIVE` |  |  | scope to one shared drive by id |
| `--max MAX` |  | `100` | maximum results (default: 100) |

### `gsuite drive search`

Search by name or raw Drive query.

```text
usage: gsuite drive search [-h] [--drive DRIVE] [--max MAX] query
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `query` | yes |  |  |
| `--drive DRIVE` |  |  | scope to one shared drive by id |
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

### `gsuite drive drives`

List shared drives.

```text
usage: gsuite drive drives [-h] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--max MAX` |  | `50` | maximum results (default: 50) |

### `gsuite drive comments`

Read and write comments on a file.

#### `gsuite drive comments list`

List comments on a file.

```text
usage: gsuite drive comments list [-h] [--include-deleted] [--max MAX] file
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `--include-deleted` |  |  | include deleted comments |
| `--max MAX` |  | `50` | maximum results (default: 50) |

#### `gsuite drive comments get`

Show one comment (--json for the reply text).

```text
usage: gsuite drive comments get [-h] file comment
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `comment` | yes |  |  |

#### `gsuite drive comments create`

Comment on a file.

```text
usage: gsuite drive comments create [-h] --content CONTENT [--quote TEXT] file
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `--content CONTENT` | yes |  |  |
| `--quote TEXT` |  |  | passage in the file the comment is about |

#### `gsuite drive comments update`

Edit a comment's text.

```text
usage: gsuite drive comments update [-h] --content CONTENT file comment
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `comment` | yes |  |  |
| `--content CONTENT` | yes |  |  |

#### `gsuite drive comments delete`

Delete a comment.

```text
usage: gsuite drive comments delete [-h] file comment
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `comment` | yes |  |  |

#### `gsuite drive comments reply`

Reply to a comment.

```text
usage: gsuite drive comments reply [-h] --content CONTENT file comment
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `comment` | yes |  |  |
| `--content CONTENT` | yes |  |  |

#### `gsuite drive comments resolve`

Mark a comment resolved.

```text
usage: gsuite drive comments resolve [-h] [--content CONTENT] file comment
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `comment` | yes |  |  |
| `--content CONTENT` |  |  | text to reply with as you resolve |

#### `gsuite drive comments reopen`

Reopen a resolved comment.

```text
usage: gsuite drive comments reopen [-h] [--content CONTENT] file comment
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `comment` | yes |  |  |
| `--content CONTENT` |  |  | text to reply with as you reopen |

### `gsuite drive revisions`

A file's version history.

#### `gsuite drive revisions list`

List a file's revisions.

```text
usage: gsuite drive revisions list [-h] [--max MAX] file
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `--max MAX` |  | `50` | maximum results (default: 50) |

#### `gsuite drive revisions get`

Show one revision.

```text
usage: gsuite drive revisions get [-h] file revision
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |
| `revision` | yes |  |  |

### `gsuite drive rename`

Rename a file or folder.

```text
usage: gsuite drive rename [-h] id name
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `name` | yes |  | the new name |

### `gsuite drive url`

Print the web URL of one or more files (no API call).

```text
usage: gsuite drive url [-h] ID [ID ...]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `ID` | yes |  |  |

### `gsuite drive unshare`

Revoke access to a file.

```text
usage: gsuite drive unshare [-h] [--with EMAIL|anyone] [--permission ID] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--with EMAIL|anyone` |  |  | the grantee whose access to revoke |
| `--permission ID` |  |  | the permission id, if you already know it |

### `gsuite drive shortcut`

Create a shortcut to a file.

```text
usage: gsuite drive shortcut [-h] [--name NAME] [--parent PARENT] target
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `target` | yes |  | id of the file to point at |
| `--name NAME` |  |  | shortcut name (default: the target's) |
| `--parent PARENT` |  |  | folder to create the shortcut in |

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

**Work through a document's comments**

```console
$ gsuite drive comments list 1DocId
$ gsuite drive comments resolve 1DocId c1 --content 'Fixed in v3.'
ID  AUTHOR  CREATED               RESOLVED  REPLIES  CONTENT
c1  Ada     2026-03-01T00:00:00Z  False     0        Cite a source?
resolved c1
```
