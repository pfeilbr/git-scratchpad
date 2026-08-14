# gsuite gmail

Search, read, send, labels, drafts.

```text
usage: gsuite gmail [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite gmail search`

Search messages (Gmail query syntax).

```text
usage: gsuite gmail search [-h] [--max MAX] query
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `query` | yes |  |  |
| `--max MAX` |  | `20` | maximum results (default: 20) |

### `gsuite gmail get`

Read a message (plain-text body).

```text
usage: gsuite gmail get [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail thread`

Read a whole thread (every message).

```text
usage: gsuite gmail thread [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail attachments`

List or download attachments.

```text
usage: gsuite gmail attachments [-h] [-o DIR] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `-o DIR, --output DIR` |  |  | download attachments into this directory |

### `gsuite gmail send`

Send an email.

```text
usage: gsuite gmail send [-h] --to TO [--subject SUBJECT] [--body BODY]
                         [--cc CC] [--bcc BCC] [--attach FILE]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--to TO` | yes |  |  |
| `--subject SUBJECT` |  |  |  |
| `--body BODY` |  |  |  |
| `--cc CC` |  |  |  |
| `--bcc BCC` |  |  |  |
| `--attach FILE` |  |  | attach a file (repeatable) |

### `gsuite gmail reply`

Reply on the original thread.

```text
usage: gsuite gmail reply [-h] --body BODY id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--body BODY` | yes |  |  |

### `gsuite gmail forward`

Forward a message.

```text
usage: gsuite gmail forward [-h] --to TO [--body BODY] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--to TO` | yes |  |  |
| `--body BODY` |  |  |  |

### `gsuite gmail archive`

Remove a message from the inbox.

```text
usage: gsuite gmail archive [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail unarchive`

Move a message back to the inbox.

```text
usage: gsuite gmail unarchive [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail mark-read`

Mark a message read.

```text
usage: gsuite gmail mark-read [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail mark-unread`

Mark a message unread.

```text
usage: gsuite gmail mark-unread [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail spam`

Mark a message as spam.

```text
usage: gsuite gmail spam [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail unspam`

Take a message out of spam.

```text
usage: gsuite gmail unspam [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail trash`

Move a message to trash.

```text
usage: gsuite gmail trash [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail untrash`

Restore a message from trash.

```text
usage: gsuite gmail untrash [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail labels`

Manage labels.

#### `gsuite gmail labels list`

```text
usage: gsuite gmail labels list [-h]
```

#### `gsuite gmail labels create`

```text
usage: gsuite gmail labels create [-h] name
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | yes |  |  |

#### `gsuite gmail labels apply`

```text
usage: gsuite gmail labels apply [-h] id label
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `label` | yes |  |  |

#### `gsuite gmail labels remove`

```text
usage: gsuite gmail labels remove [-h] id label
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `label` | yes |  |  |

### `gsuite gmail drafts`

Manage drafts.

#### `gsuite gmail drafts list`

```text
usage: gsuite gmail drafts list [-h]
```

#### `gsuite gmail drafts create`

```text
usage: gsuite gmail drafts create [-h] --to TO [--subject SUBJECT]
                                  [--body BODY] [--cc CC] [--bcc BCC]
                                  [--attach FILE]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--to TO` | yes |  |  |
| `--subject SUBJECT` |  |  |  |
| `--body BODY` |  |  |  |
| `--cc CC` |  |  |  |
| `--bcc BCC` |  |  |  |
| `--attach FILE` |  |  | attach a file (repeatable) |

### `gsuite gmail vacation`

Auto-reply (vacation responder) settings.

#### `gsuite gmail vacation show`

```text
usage: gsuite gmail vacation show [-h]
```

#### `gsuite gmail vacation set`

```text
usage: gsuite gmail vacation set [-h] --subject SUBJECT --body BODY
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--subject SUBJECT` | yes |  |  |
| `--body BODY` | yes |  |  |

#### `gsuite gmail vacation off`

```text
usage: gsuite gmail vacation off [-h]
```

### `gsuite gmail signature`

Send-as signatures.

#### `gsuite gmail signature show`

```text
usage: gsuite gmail signature show [-h] [--send-as EMAIL]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--send-as EMAIL` |  |  | send-as address (default: primary) |

#### `gsuite gmail signature set`

```text
usage: gsuite gmail signature set [-h] --html HTML [--send-as EMAIL]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--html HTML` | yes |  |  |
| `--send-as EMAIL` |  |  | send-as address (default: primary) |

### `gsuite gmail filters`

Manage filters.

#### `gsuite gmail filters list`

```text
usage: gsuite gmail filters list [-h]
```

#### `gsuite gmail filters create`

```text
usage: gsuite gmail filters create [-h] [--from FROM] [--query QUERY]
                                   [--add-label NAME] [--delete]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--from FROM` |  |  | match sender |
| `--query QUERY` |  |  | match a Gmail search query |
| `--add-label NAME` |  |  | apply this label to matches |
| `--delete` |  |  | send matches to trash |

#### `gsuite gmail filters rm`

```text
usage: gsuite gmail filters rm [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite gmail batch-modify`

Add/remove a label across all query matches.

```text
usage: gsuite gmail batch-modify [-h] --query QUERY [--add-label NAME]
                                 [--remove-label NAME] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--query QUERY` | yes |  |  |
| `--add-label NAME` |  |  |  |
| `--remove-label NAME` |  |  |  |
| `--max MAX` |  | `500` | maximum results (default: 500) |

## Examples

**Find unread mail from a sender**

```console
$ gsuite gmail search 'is:unread from:alice@example.com' --max 5
ID      DATE                    FROM               SUBJECT
19ab3f  Mon, 5 Jan 2026 09:14   alice@example.com  Q1 roadmap
```

**Send an email**

```console
$ gsuite gmail send --to bob@example.com --subject "Lunch?" --body "12:30 at the usual spot"
sent 19ab41
```

**Reply within the original thread**

```console
$ gsuite gmail reply 19ab3f --body "Sounds good — shipping Friday."
sent 19ab42
```

**Label triage**

```console
$ gsuite gmail labels create follow-up
$ gsuite gmail labels apply 19ab3f follow-up
applied follow-up to 19ab3f
```
