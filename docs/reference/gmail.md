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

### `gsuite gmail triage`

Summarize unread inbox mail.

```text
usage: gsuite gmail triage [-h] [--max MAX]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
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

Reply to the sender, on the original thread.

```text
usage: gsuite gmail reply [-h] --body BODY id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--body BODY` | yes |  |  |

### `gsuite gmail reply-all`

Reply to every participant, on the original thread.

```text
usage: gsuite gmail reply-all [-h] --body BODY id
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

### `gsuite gmail settings`

Mailbox settings: send-as, delegates, forwarding.

#### `gsuite gmail settings sendas`

Send-as addresses.

##### `gsuite gmail settings sendas list`

List send-as addresses.

```text
usage: gsuite gmail settings sendas list [-h]
```

##### `gsuite gmail settings sendas get`

Show one send-as address.

```text
usage: gsuite gmail settings sendas get [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

##### `gsuite gmail settings sendas create`

Add a send-as address.

```text
usage: gsuite gmail settings sendas create [-h] [--name DISPLAY]
                                           [--reply-to EMAIL]
                                           [--treat-as-alias]
                                           email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |
| `--name DISPLAY` |  |  | display name on outgoing mail |
| `--reply-to EMAIL` |  |  | address replies should go to |
| `--treat-as-alias` |  |  | treat mail to this address as mail to you |

##### `gsuite gmail settings sendas update`

Change a send-as address.

```text
usage: gsuite gmail settings sendas update [-h] [--name DISPLAY]
                                           [--reply-to EMAIL] [--default]
                                           email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |
| `--name DISPLAY` |  |  | display name on outgoing mail |
| `--reply-to EMAIL` |  |  | address replies should go to |
| `--default` |  |  | send new mail from this address by default |

##### `gsuite gmail settings sendas delete`

Remove a send-as address.

```text
usage: gsuite gmail settings sendas delete [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

##### `gsuite gmail settings sendas verify`

Send the ownership confirmation mail again.

```text
usage: gsuite gmail settings sendas verify [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

#### `gsuite gmail settings delegates`

People who may read and send as this mailbox.

##### `gsuite gmail settings delegates list`

List delegates.

```text
usage: gsuite gmail settings delegates list [-h]
```

##### `gsuite gmail settings delegates get`

Show one delegate.

```text
usage: gsuite gmail settings delegates get [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

##### `gsuite gmail settings delegates add`

Grant delegate access.

```text
usage: gsuite gmail settings delegates add [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

##### `gsuite gmail settings delegates remove`

Revoke delegate access.

```text
usage: gsuite gmail settings delegates remove [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

#### `gsuite gmail settings forwarding`

Addresses this mailbox may forward to.

##### `gsuite gmail settings forwarding list`

List forwarding addresses.

```text
usage: gsuite gmail settings forwarding list [-h]
```

##### `gsuite gmail settings forwarding get`

Show one forwarding address.

```text
usage: gsuite gmail settings forwarding get [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

##### `gsuite gmail settings forwarding create`

Add a forwarding address.

```text
usage: gsuite gmail settings forwarding create [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

##### `gsuite gmail settings forwarding delete`

Remove a forwarding address.

```text
usage: gsuite gmail settings forwarding delete [-h] email
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `email` | yes |  |  |

#### `gsuite gmail settings autoforward`

Forward incoming mail automatically.

##### `gsuite gmail settings autoforward get`

Show the auto-forwarding rule.

```text
usage: gsuite gmail settings autoforward get [-h]
```

##### `gsuite gmail settings autoforward update`

Set the auto-forwarding rule.

```text
usage: gsuite gmail settings autoforward update [-h] [--to EMAIL]
                                                [--disposition {leaveInInbox,archive,trash,markRead}]
                                                [--off]
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--to EMAIL` |  |  | forward to this address (it must already be verified: `gsuite gmail settings forwarding list`) |
| `--disposition {leaveInInbox,archive,trash,markRead}` |  | `leaveInInbox` | what to do with the original copy |
| `--off` |  |  | stop forwarding incoming mail |

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

**Triage the unread inbox**

```console
$ gsuite gmail triage --max 3
ID      FROM               SUBJECT        DATE
19ab3f  alice@example.com  Q1 roadmap     Mon, 5 Jan 2026 09:14
19ab40  ci@example.com     Build #412 ok  Mon, 5 Jan 2026 08:02
```

**Reply within the original thread**

```console
$ gsuite gmail reply 19ab3f --body "Sounds good — shipping Friday."
$ gsuite gmail reply-all 19ab3f --body "Looping in the whole thread."
sent 19ab42
```

**Label triage**

```console
$ gsuite gmail labels create follow-up
$ gsuite gmail labels apply 19ab3f follow-up
applied follow-up to 19ab3f
```

**Forward incoming mail to an address that has confirmed itself**

```console
$ gsuite gmail settings forwarding list
$ gsuite gmail settings autoforward update --to ops@example.com --disposition archive
auto-forwarding to ops@example.com (archive)
```
