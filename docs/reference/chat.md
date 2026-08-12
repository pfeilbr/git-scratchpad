# gsuite chat

Google Chat spaces and messages.

```text
usage: gsuite chat [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite chat spaces`

List spaces.

```text
usage: gsuite chat spaces [-h]
```

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

## Examples

**Message a space**

```console
$ gsuite chat spaces
$ gsuite chat send spaces/AAAA --text 'Deploy done ✅'
sent spaces/AAAA/messages/BBBB.CCCC
```
