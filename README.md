<h1 align="center">LinXfus</h1>
<p align="center"><b>Rufus, version Linux.</b> Clés USB bootables Windows, macOS et Linux en une commande.</p>
<p align="center">
  <a href="https://joss943.github.io/Linxfus/">Site</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#sécurité">Sécurité</a><br><br>
  <a href="https://github.com/Joss943/Linxfus/actions/workflows/ci.yml"><img src="https://github.com/Joss943/Linxfus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/bash-1%20fichier%20~30%20Ko-7ee787" alt="1 fichier">
  <img src="https://img.shields.io/badge/licence-MIT-blue" alt="MIT">
</p>

---

LinXfus est un script bash autonome qui fait sous Linux ce que Rufus fait sous Windows. Tu lui donnes une image et une clé : il reconnaît le type d'image, prépare la clé avec la bonne méthode et vérifie tout ce qui peut l'être. Il ne touche jamais à ton disque système.

```console
$ sudo linxfus -i Win11.iso -d /dev/sdb --win11-bypass
```

## Fonctionnalités

| | Méthode | Démarre en |
|---|---|---|
| **Windows 7 → 11** | MBR ou GPT + FAT32, `install.wim` > 4 Go découpé en `.swm` (wimlib), GRUB → `bootmgr` pour le BIOS, `--win11-bypass` (TPM / Secure Boot / RAM) | BIOS + UEFI (MBR) · UEFI (GPT) |
| **Linux** et images brutes | `dd` direct (O_DIRECT, 4 Mo), `.xz .gz .zst .bz2` décompressés à la volée et en multi-cœur, relecture `-V` | celui de l'image |
| **macOS** | recovery officielle téléchargée chez Apple (`--mac-recovery`), vérifiée par la chunklist signée par Apple ; mode `raw` (Mac Intel) ou `opencore` (Hackintosh) | Mac Intel · OpenCore |

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/Joss943/Linxfus/main/linxfus | sudo install -m755 /dev/stdin /usr/local/bin/linxfus && sudo linxfus --deps
```

`--deps` installe les dépendances via `dnf`, `apt` ou `pacman` : parted, dosfstools, rsync, wimlib, GRUB i386-pc, dmg2img, python3, curl. Pour Linux, util-linux et coreutils suffisent ; Windows demande parted et dosfstools ; le reste n'est réclamé que si un cas en a besoin.

## Usage

```bash
linxfus -l                                         # clés USB branchées
sudo linxfus                                       # mode guidé
sudo linxfus -i Win11.iso -d /dev/sdb --win11-bypass
sudo linxfus -i Win10.iso -d /dev/sdb -s gpt       # UEFI uniquement
sudo linxfus -i Fedora.iso -d /dev/sdb --sha256 <hash> -V
sudo linxfus -i raspios.img.xz -d /dev/sdb
sudo linxfus --mac-recovery sonoma -d /dev/sdb
sudo linxfus --mac-recovery sequoia --mac-mode opencore --efi ./EFI -d /dev/sdb
```

<details>
<summary>Toutes les options</summary>

```
-i, --image FICHIER     ISO / IMG / DMG (.xz .gz .zst .bz2 acceptés)
-d, --device DISQUE     clé cible, disque entier (/dev/sdX)
-t, --type TYPE         auto | windows | mac | linux
-L, --label NOM         nom du volume (Windows / OpenCore)
    --sha256 HASH       vérifie l'image avant écriture
-V, --verify            relit la clé après écriture (images brutes)
-y, --yes               pas de confirmation
-f, --force             autorise un disque non amovible ou monté ailleurs
-l, --list              liste les clés USB
    --deps              installe les dépendances

Windows : -s mbr|gpt · --no-bios · --win11-bypass
macOS   : --mac-recovery VER · --mac-mode raw|opencore · --efi DOSSIER
          VER = elcapitan sierra highsierra mojave catalina bigsur
                monterey ventura sonoma sequoia tahoe
```
</details>

## Sécurité

- **Disque système intouchable** : `/`, `/boot`, `/home`, swap, y compris derrière LVM ou LUKS.
- **Cible contrôlée** : disque entier uniquement, amovible, pas monté hors `/media` ou `/mnt` (sinon `--force`).
- **Confirmation** : récapitulatif + `OUI`, puis re-vérification de l'identité de la clé (numéro, taille, modèle) juste avant d'écrire. Une clé échangée entre-temps n'est pas effacée.
- **Rien n'est effacé pour rien** : un DMG illisible est détecté avant d'effacer la clé.
- **Code externe épinglé** : le seul script téléchargé (macrecovery d'OpenCorePkg 1.0.8) est vérifié par SHA-256 avant exécution, avec `python3 -I`. Les images Apple sont vérifiées contre la chunklist signée par Apple, cache compris.
- **Exécution durcie** : `PATH` figé, `umask 077`, montages `nosuid,nodev,noexec`, pas d'`eval`, nettoyage automatique même après Ctrl+C ou erreur.
- **CI** : shellcheck + tests d'intégration sur loop device à chaque commit, actions GitHub épinglées par SHA.

## Limites

- **Mac Apple Silicon** : ils ne démarrent pas sur ces clés. Il faut `createinstallmedia` depuis un Mac.
- **macOS en mode `raw`** : fiable jusqu'à Catalina. Au-delà, les DMG sont en LZFSE et `dmg2img` des distributions ne les lit pas : utiliser `--mac-mode opencore`.
- **`--win11-bypass`** : méthode LabConfig (comme Rufus), pour une installation propre. Microsoft peut la casser dans une future version.
- **Pas de persistance** pour les live USB Linux. Pour ça, Ventoy.

## Tests

```bash
sudo tests/run.sh    # 27 tests sur un loop device : Windows MBR/GPT, découpage WIM, dd, xz, OpenCore, garde-fous
```

## Licence

MIT © Josselin Lerendu
