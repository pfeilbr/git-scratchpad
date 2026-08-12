# gsuite contacts

List, search, create contacts.

```text
usage: gsuite contacts [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

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

### `gsuite contacts rm`

Delete a contact by resource name.

```text
usage: gsuite contacts rm [-h] resource
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `resource` | yes |  | e.g. people/c123 |

## Examples

**Search, then add a contact**

```console
$ gsuite contacts search ada
$ gsuite contacts create --name 'Ada Lovelace' --email ada@example.com
created people/c123
```
