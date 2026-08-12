# gsuite admin

Workspace admin: users, groups.

```text
usage: gsuite admin [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite admin users`

Manage users.

#### `gsuite admin users list`

```text
usage: gsuite admin users list [-h] [--query QUERY] [--domain DOMAIN]
                               [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--query QUERY` |  |  | Directory API query, e.g. name:Jane |
| `--domain DOMAIN` |  |  |  |
| `--max MAX` |  | `100` | maximum results (default: 100) |

#### `gsuite admin users info`

```text
usage: gsuite admin users info [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

#### `gsuite admin users create`

```text
usage: gsuite admin users create [-h] --email EMAIL --first FIRST --last LAST
                                 --password PASSWORD
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--email EMAIL` | yes |  |  |
| `--first FIRST` | yes |  |  |
| `--last LAST` | yes |  |  |
| `--password PASSWORD` | yes |  |  |

#### `gsuite admin users suspend`

```text
usage: gsuite admin users suspend [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

#### `gsuite admin users unsuspend`

```text
usage: gsuite admin users unsuspend [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

#### `gsuite admin users delete`

```text
usage: gsuite admin users delete [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

### `gsuite admin groups`

Manage groups.

#### `gsuite admin groups list`

```text
usage: gsuite admin groups list [-h] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--max MAX` |  | `100` | maximum results (default: 100) |

#### `gsuite admin groups create`

```text
usage: gsuite admin groups create [-h] --email EMAIL [--name NAME]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--email EMAIL` | yes |  |  |
| `--name NAME` |  |  |  |

#### `gsuite admin groups members`

```text
usage: gsuite admin groups members [-h] group
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `group` | yes |  |  |

#### `gsuite admin groups add-member`

```text
usage: gsuite admin groups add-member [-h] [--role {MEMBER,MANAGER,OWNER}]
                                      group email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `group` | yes |  |  |
| `email` | yes |  |  |
| `--role {MEMBER,MANAGER,OWNER}` |  | `MEMBER` |  |

## Examples

**Onboard a user and add them to a group**

```console
$ gsuite admin users create --email new@corp.com --first New --last Person --password 'temp-Passw0rd!'
$ gsuite admin groups add-member eng@corp.com new@corp.com
added new@corp.com to eng@corp.com
```

**Find suspended accounts**

```console
$ gsuite --json admin users list --query 'isSuspended=true'
[
  {"primaryEmail": "left@corp.com", "suspended": true}
]
```
