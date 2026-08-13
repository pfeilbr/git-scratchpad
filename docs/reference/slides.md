# gsuite slides

Presentations: create, info, cat, add.

```text
usage: gsuite slides [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite slides create`

Create a presentation.

```text
usage: gsuite slides create [-h] --title TITLE
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--title TITLE` | yes |  |  |

### `gsuite slides info`

Show title and slide count.

```text
usage: gsuite slides info [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite slides cat`

Print each slide's text.

```text
usage: gsuite slides cat [-h] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |

### `gsuite slides add`

Append a title-and-body slide.

```text
usage: gsuite slides add [-h] --title TITLE [--body BODY] id
```

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `id` | yes |  |  |
| `--title TITLE` | yes |  |  |
| `--body BODY` |  |  | body placeholder text |

## Examples

**Create a deck and inspect it**

```console
$ gsuite slides create --title 'Q1 review'
$ gsuite slides info 1PresId
id: 1PresId
title: Q1 review
slides: 1
```
