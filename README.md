# LinXfus

L'équivalent de **Rufus** pour Linux, en une seule commande : clés USB bootables **Windows**, **macOS** et **Linux**.
Le type d'image est détecté tout seul et la bonne méthode d'écriture est choisie.

```bash
sudo linxfus                                   # mode interactif
sudo linxfus -i Win11.iso -d /dev/sdb --win11-bypass
```

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/Joss943/linxfus/main/linxfus | sudo install -m755 /dev/stdin /usr/local/bin/linxfus && sudo linxfus --deps
```

`--deps` installe les dépendances via `dnf`, `apt` ou `pacman` (parted, dosfstools, rsync, wimlib, GRUB i386-pc, dmg2img, python3, curl).

## Ce que ça fait

| Image | Méthode | Démarrage |
|---|---|---|
| **Windows** 7 → 11 (ISO) | MBR ou GPT + FAT32, copie des fichiers, `install.wim` > 4 Go découpé en `.swm` (wimlib), GRUB → `bootmgr` pour le BIOS | UEFI + BIOS (MBR) · UEFI seul (GPT) |
| **Linux** (ISO hybride, `.img`, `.img.xz/.gz/.zst/.bz2`) | écriture brute `dd`, décompression à la volée, relecture `-V` | celui de l'image |
| **macOS** `.dmg` / recovery | `dmg2img` → écriture brute (mode `raw`) ou FAT32 + `com.apple.recovery.boot` (mode `opencore`) | Mac Intel · Hackintosh (OpenCore) |

Pour macOS, `--mac-recovery <version>` télécharge la recovery officielle depuis les serveurs Apple via [macrecovery](https://github.com/acidanthera/OpenCorePkg/tree/master/Utilities/macrecovery) (OpenCorePkg), vérifiée par chunklist et mise en cache dans `/var/cache/linxfus`.
Versions : `elcapitan sierra highsierra mojave catalina bigsur monterey ventura sonoma sequoia tahoe`.

## Options

```
-i, --image FICHIER     ISO / IMG / DMG
-d, --device DISQUE     clé cible (/dev/sdX, disque entier)
-t, --type TYPE         auto | windows | mac | linux
-L, --label NOM         nom du volume
    --sha256 HASH       vérifie l'image avant écriture
-V, --verify            relit la clé après écriture (modes dd)
-y, --yes               pas de confirmation
-f, --force             autorise un disque non amovible
-l, --list              liste les clés USB
    --deps              installe les dépendances

Windows : -s mbr|gpt · --no-bios · --win11-bypass (TPM / Secure Boot / RAM)
macOS   : --mac-recovery VER · --mac-mode raw|opencore · --efi DOSSIER
```

## Exemples

```bash
linxfus -l                                                   # quelles clés sont branchées ?
sudo linxfus -i Fedora-Workstation-Live.iso -d /dev/sdb -V
sudo linxfus -i raspios.img.xz -d /dev/sdb
sudo linxfus -i Win10.iso -d /dev/sdb -s gpt
sudo linxfus --mac-recovery sonoma -d /dev/sdb
sudo linxfus --mac-recovery sequoia --mac-mode opencore --efi ./EFI -d /dev/sdb
```

## Sécurité

- Refuse les disques qui portent le système (`/`, `/boot`, `/home`, swap, y compris via LVM/LUKS).
- Refuse les disques non amovibles sans `--force`, et les partitions (il faut le disque entier).
- Récapitulatif + saisie de `OUI` avant d'effacer quoi que ce soit.
- Démonte proprement la clé et nettoie tout en cas d'erreur ou de Ctrl+C.

## Limites

- **Mac Apple Silicon** : ils ne démarrent pas sur ces clés. Il faut `createinstallmedia` depuis un Mac (ou la recovery intégrée).
- **macOS en mode `raw`** : sûr jusqu'à Catalina. Les DMG récents (Big Sur +) utilisent LZFSE, que `dmg2img` des distributions ne décompresse pas toujours → utiliser `--mac-mode opencore` dans ce cas.
- **`--win11-bypass`** : méthode LabConfig (comme Rufus) pour une installation propre. Microsoft peut la casser dans de futures versions.
- **ISO Linux non hybride** : écrite telle quelle, elle risque de ne pas démarrer (LinXfus prévient).
- Pas de persistance pour les live USB Linux (pour ça : Ventoy).

## Licence

MIT
