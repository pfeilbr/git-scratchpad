# gsuite api

Raw calls to any Google API.

```text
usage: gsuite api [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`, `--timeout TIMEOUT`.

## Commands

### `gsuite api call`

Authorized request to any endpoint.

```text
usage: gsuite api call [-h] [--param KEY=VALUE] [--body BODY] method path
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `method` | yes |  | GET/POST/PATCH/PUT/DELETE |
| `path` | yes |  | full URL or path under www.googleapis.com (e.g. drive/v3/about) |
| `--param KEY=VALUE` |  |  | query parameter; repeat for more than one, and repeat the same key to send it more than once |
| `--body BODY` |  |  | JSON request body (@file reads from a file, - reads from stdin) |

### `gsuite api describe`

List an API's methods (Discovery service).

```text
usage: gsuite api describe [-h] [--api-version API_VERSION] service
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `service` | yes |  | e.g. gmail, drive, tasks |
| `--api-version API_VERSION` |  |  | e.g. v1 (default: preferred) |

### `gsuite api list`

List available Google APIs.

```text
usage: gsuite api list [-h]
```

## Examples

**Call any endpoint (no dedicated command needed)**

```console
$ gsuite api call GET drive/v3/about --param fields=user
{
  "user": {
    "emailAddress": "you@example.com"
  }
}
```

**Discover what an API offers**

```console
$ gsuite api describe forms
METHOD               HTTP  PATH             DESCRIPTION
forms.forms.create   POST  v1/forms         Create a new form.
```
