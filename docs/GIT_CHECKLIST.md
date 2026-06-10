# Git-Checkliste

Vor dem Upload prüfen:

```bash
grep -RInE '192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.' . --exclude-dir=.git || true
find . -name '__pycache__' -o -name '*.pyc'
find . -name '*.sqlite' -o -name '*.db'
```

Committen:

```bash
git init
git branch -M main
git add .
git commit -m "Initial AETHORIA Companion v0.97"
```
