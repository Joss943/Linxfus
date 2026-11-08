#!/usr/bin/env bash
# Installe LinXfus (application + moteur) :
#   curl -fsSL https://raw.githubusercontent.com/Joss943/Linxfus/main/install.sh | sudo bash
# Désinstaller : ... | sudo bash -s -- --uninstall
set -euo pipefail
umask 022
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RAW=https://raw.githubusercontent.com/Joss943/Linxfus/main
ID=io.github.joss943.Linxfus
DEST=(
  "linxfus:/usr/local/bin/linxfus:755"
  "linxfus-gui:/usr/local/bin/linxfus-gui:755"
  "data/$ID.desktop:/usr/local/share/applications/$ID.desktop:644"
  "data/$ID.svg:/usr/local/share/icons/hicolor/scalable/apps/$ID.svg:644"
  "data/io.github.joss943.linxfus.policy:/usr/share/polkit-1/actions/io.github.joss943.linxfus.policy:644"
)
((EUID == 0)) || { echo "Lance l'installation avec sudo." >&2; exit 1; }

refresh() {
  gtk-update-icon-cache -qtf /usr/local/share/icons/hicolor 2>/dev/null || true
  update-desktop-database -q /usr/local/share/applications 2>/dev/null || true
}

if [[ ${1:-} == --uninstall ]]; then
  for e in "${DEST[@]}"; do IFS=: read -r _ dst _ <<<"$e"; rm -f -- "$dst"; done
  rm -rf /var/cache/linxfus
  refresh
  echo "LinXfus désinstallé."; exit 0
fi

# Fichiers : depuis le dossier du script (clone git) ou téléchargés depuis GitHub.
SRC=$(dirname "$(readlink -f "${BASH_SOURCE[0]:-/dev/null}")")
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
for e in "${DEST[@]}"; do
  IFS=: read -r src dst mode <<<"$e"
  if [[ -f $SRC/$src && -f $SRC/linxfus-gui ]]; then cp -- "$SRC/$src" "$TMP/${src##*/}"
  else curl -fsSL --proto '=https' --tlsv1.2 -o "$TMP/${src##*/}" "$RAW/$src"; fi
  install -Dm"$mode" -- "$TMP/${src##*/}" "$dst"
done

echo "Dépendances de l'interface (GTK 4, PyGObject, polkit)…"
if command -v dnf >/dev/null; then
  dnf install -y python3-gobject gtk4 polkit
elif command -v apt-get >/dev/null; then
  apt-get update -q && apt-get install -y python3-gi gir1.2-gtk-4.0 && { apt-get install -y pkexec 2>/dev/null || apt-get install -y policykit-1; }
elif command -v pacman >/dev/null; then
  pacman -S --needed --noconfirm python-gobject gtk4 polkit
else
  echo "Gestionnaire de paquets non géré : installe PyGObject, GTK 4 et polkit." >&2
fi
/usr/local/bin/linxfus --deps
refresh
echo
echo "✓ LinXfus installé. Ouvre « LinXfus » dans tes applications (ou lance : linxfus-gui)."
