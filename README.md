# Gatekeeper readme

Keeps internet connection open if possible (Restarts network LTE modem)

# Package creation

## Archlinux

```bash
cd archlinux
makepkg
```

## Debian

```bash
python3 setup.py --command-packages=stdeb.command bdist_deb
```
