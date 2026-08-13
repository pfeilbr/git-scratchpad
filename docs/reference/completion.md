# gsuite completion

Shell tab-completion (generated from the parser tree).

```text
usage: gsuite completion [-h] <command> ...
```

Global flags `-a/--account <email|alias>` and `--json` go *before* the service name.

## Commands

### `gsuite completion bash`

Print a bash completion script.

```text
usage: gsuite completion bash [-h]
```

### `gsuite completion zsh`

Print a zsh completion script (bashcompinit shim).

```text
usage: gsuite completion zsh [-h]
```

## Examples

**Enable bash completion (add the source line to ~/.bashrc to persist)**

```console
$ source <(gsuite completion bash)
$ gsuite completion bash | tail -1
complete -F _gsuite gsuite
```

**zsh reuses the same script via the bashcompinit shim**

```console
$ source <(gsuite completion zsh)
$ gsuite completion zsh | head -1
autoload -U +X bashcompinit && bashcompinit
```
