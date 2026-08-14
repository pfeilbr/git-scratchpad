# gsuite auth

Login, accounts, aliases, tokens.

```text
usage: gsuite auth [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite auth login`

Sign in via browser (loopback OAuth).

```text
usage: gsuite auth login [-h] [--services SERVICES] [email]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` |  |  | account email (auto-detected if omitted) |
| `--services SERVICES` |  |  | comma-separated services to authorize, or `all` for every service (default: gmail,calendar,drive,contacts) |

### `gsuite auth logout`

Revoke the token at Google, then remove the account locally.

```text
usage: gsuite auth logout [-h] [--no-revoke] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |
| `--no-revoke` |  |  | remove the account locally without revoking its token at Google (offline, or deliberately keeping it alive) |

### `gsuite auth revoke`

Revoke an account's token at Google, keeping the account.

```text
usage: gsuite auth revoke [-h] [email]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` |  |  | account email or alias (default: the default account) |

### `gsuite auth list`

List accounts.

```text
usage: gsuite auth list [-h]
```

### `gsuite auth status`

Show current account and token state.

```text
usage: gsuite auth status [-h]
```

### `gsuite auth switch`

Set the default account.

```text
usage: gsuite auth switch [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

### `gsuite auth alias`

Manage account aliases.

#### `gsuite auth alias set`

```text
usage: gsuite auth alias set [-h] name email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | yes |  |  |
| `email` | yes |  |  |

#### `gsuite auth alias rm`

```text
usage: gsuite auth alias rm [-h] name
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | yes |  |  |

#### `gsuite auth alias list`

```text
usage: gsuite auth alias list [-h]
```

### `gsuite auth credentials`

Manage the OAuth client.

#### `gsuite auth credentials set`

Store a Desktop-app OAuth client JSON.

```text
usage: gsuite auth credentials set [-h] file
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes |  |  |

### `gsuite auth token`

Print a fresh access token (for scripts).

```text
usage: gsuite auth token [-h]
```

### `gsuite auth adc`

Show Application Default Credentials status.

```text
usage: gsuite auth adc [-h]
```

### `gsuite auth doctor`

Diagnose auth setup.

```text
usage: gsuite auth doctor [-h]
```

## Examples

**First login (browser opens, email auto-detected)**

```console
$ gsuite auth login --services gmail,calendar,drive
Logged in as you@example.com (services: calendar, drive, gmail)
```

**Multiple accounts with aliases**

```console
$ gsuite auth login work@corp.com
$ gsuite auth alias set work work@corp.com
$ gsuite -a work auth status
account: work@corp.com
token: valid
```

**Diagnose a broken setup**

```console
$ gsuite auth doctor
OK   OAuth client configured
OK   at least one account
OK   token usable: you@example.com
```
