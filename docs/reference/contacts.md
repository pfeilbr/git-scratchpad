# gsuite contacts

List, search, create contacts.

```text
usage: gsuite contacts [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite contacts list`

List contacts.

```text
usage: gsuite contacts list [-h] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--max MAX` |  | `100` | maximum results (default: 100) |

### `gsuite contacts search`

Search contacts.

```text
usage: gsuite contacts search [-h] query
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `query` | yes |  |  |

### `gsuite contacts get`

Show one contact.

```text
usage: gsuite contacts get [-h] resource
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `resource` | yes |  | e.g. people/c123 |

### `gsuite contacts create`

Create a contact.

```text
usage: gsuite contacts create [-h] --name NAME [--email EMAIL] [--phone PHONE]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--name NAME` | yes |  |  |
| `--email EMAIL` |  |  |  |
| `--phone PHONE` |  |  |  |

### `gsuite contacts update`

Update contact fields.

```text
usage: gsuite contacts update [-h] [--name NAME] [--email EMAIL]
                              [--phone PHONE]
                              resource
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `resource` | yes |  | e.g. people/c123 |
| `--name NAME` |  |  |  |
| `--email EMAIL` |  |  |  |
| `--phone PHONE` |  |  |  |

### `gsuite contacts rm`

Delete a contact by resource name.

```text
usage: gsuite contacts rm [-h] resource
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `resource` | yes |  | e.g. people/c123 |

### `gsuite contacts groups`

Manage contact groups.

#### `gsuite contacts groups list`

List contact groups.

```text
usage: gsuite contacts groups list [-h]
```

#### `gsuite contacts groups create`

Create a contact group.

```text
usage: gsuite contacts groups create [-h] --name NAME
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--name NAME` | yes |  |  |

#### `gsuite contacts groups add`

Add a person to a group.

```text
usage: gsuite contacts groups add [-h] group person
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `group` | yes |  | e.g. contactGroups/abc |
| `person` | yes |  | e.g. people/c123 |

## Examples

**Search, then add a contact**

```console
$ gsuite contacts search ada
$ gsuite contacts create --name 'Ada Lovelace' --email ada@example.com
created people/c123
```
