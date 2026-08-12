# gsuite slides

Presentations: create, info.

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

## Examples

**Create a deck and inspect it**

```console
$ gsuite slides create --title 'Q1 review'
$ gsuite slides info 1PresId
id: 1PresId
title: Q1 review
slides: 1
```
