# gsuite sheets

Spreadsheets: read/append/update.

```text
usage: gsuite sheets [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite sheets create`

Create a spreadsheet.

```text
usage: gsuite sheets create [-h] --title TITLE
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--title TITLE` | yes |  |  |

### `gsuite sheets read`

Print a range (tab-separated).

```text
usage: gsuite sheets read [-h] id range
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `range` | yes |  | A1 notation, e.g. Sheet1!A1:B10 |

### `gsuite sheets append`

Append rows after a range.

```text
usage: gsuite sheets append [-h] --values VALUES id range
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `range` | yes |  | A1 notation, e.g. Sheet1!A1:B10 |
| `--values VALUES` | yes |  | rows separated by ';', cells by ',' |

### `gsuite sheets update`

Overwrite a range.

```text
usage: gsuite sheets update [-h] --values VALUES id range
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `range` | yes |  | A1 notation, e.g. Sheet1!A1:B10 |
| `--values VALUES` | yes |  | rows separated by ';', cells by ',' |

### `gsuite sheets clear`

Clear a range.

```text
usage: gsuite sheets clear [-h] id range
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `range` | yes |  | A1 notation, e.g. Sheet1!A1:B10 |

### `gsuite sheets tabs`

List tabs (sheets) in a spreadsheet.

```text
usage: gsuite sheets tabs [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite sheets add-tab`

Add a tab.

```text
usage: gsuite sheets add-tab [-h] --title TITLE id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--title TITLE` | yes |  |  |

### `gsuite sheets rm-tab`

Remove a tab.

```text
usage: gsuite sheets rm-tab [-h] --tab TAB id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--tab TAB` | yes |  | numeric sheet id (see `sheets tabs`) |

## Examples

**Append rows, then read a range**

```console
$ gsuite sheets append 1SheetId 'Sheet1!A1' --values 'jan,100;feb,120'
$ gsuite sheets read 1SheetId 'Sheet1!A1:B2'
jan	100
feb	120
```
