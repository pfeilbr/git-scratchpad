# gsuite chat

Google Chat spaces and messages.

```text
usage: gsuite chat [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite chat spaces`

List spaces.

```text
usage: gsuite chat spaces [-h]
```

### `gsuite chat create-space`

Create a space.

```text
usage: gsuite chat create-space [-h] --name NAME [--type {SPACE,GROUP_CHAT}]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--name NAME` | yes |  | display name |
| `--type {SPACE,GROUP_CHAT}` |  | `SPACE` |  |

### `gsuite chat members`

List members of a space.

```text
usage: gsuite chat members [-h] space
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `space` | yes |  | e.g. spaces/AAAA |

### `gsuite chat add-member`

Add a user to a space.

```text
usage: gsuite chat add-member [-h] space user
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `space` | yes |  |  |
| `user` | yes |  | user id or users/<id> |

### `gsuite chat messages`

List messages in a space.

```text
usage: gsuite chat messages [-h] [--max MAX] space
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `space` | yes |  | e.g. spaces/AAAA |
| `--max MAX` |  | `50` | maximum results (default: 50) |

### `gsuite chat send`

Send a text message to a space.

```text
usage: gsuite chat send [-h] --text TEXT space
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `space` | yes |  |  |
| `--text TEXT` | yes |  |  |

### `gsuite chat reply`

Reply in a message thread.

```text
usage: gsuite chat reply [-h] --thread THREAD --text TEXT space
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `space` | yes |  |  |
| `--thread THREAD` | yes |  | e.g. spaces/AAAA/threads/TTTT |
| `--text TEXT` | yes |  |  |

## Examples

**Message a space**

```console
$ gsuite chat spaces
$ gsuite chat send spaces/AAAA --text 'Deploy done ✅'
sent spaces/AAAA/messages/BBBB.CCCC
```
