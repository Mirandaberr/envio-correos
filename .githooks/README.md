# Git hooks versionados

`commit-msg` valida que los mensajes sigan Conventional Commits
(`tipo(alcance): descripción`).

Cada clon nuevo debe activarlos una vez:

```bash
git config core.hooksPath .githooks
```
