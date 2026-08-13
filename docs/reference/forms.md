# gsuite forms

Google Forms: create, inspect, responses.

```text
usage: gsuite forms [-h] <command> ...
```

Global flags go *before* the service name: `-a/--account ACCOUNT`, `--json`, `--readonly`, `--csv`, `--fields FIELDS`, `--debug`.

## Commands

### `gsuite forms create`

Create a form.

```text
usage: gsuite forms create [-h] --title TITLE
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--title TITLE` | yes |  |  |

### `gsuite forms get`

Show form metadata.

```text
usage: gsuite forms get [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite forms questions`

List a form's questions.

```text
usage: gsuite forms questions [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite forms responses`

List form responses.

```text
usage: gsuite forms responses [-h] [--max MAX] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--max MAX` |  | `50` | maximum results (default: 50) |

## Examples

**Create a form and inspect it**

```console
$ gsuite forms create --title 'Team survey'
$ gsuite forms get 1FormId
id: 1FormId
title: Team survey
url: https://docs.google.com/forms/d/e/…/viewform
items: 0
```

**Review the latest responses**

```console
$ gsuite forms responses 1FormId --max 2
ID    SUBMITTED
r9a1  2026-01-05T10:00:00Z
r9a2  2026-01-06T11:30:00Z
```
