#!/usr/bin/env bash
# Tests d'intégration LinXfus sur un loop device (root requis) : sudo tests/run.sh
# REQUIRE_BIOS=1 : échoue si le chargeur BIOS (grub-install) n'a pas pu être installé.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d) LOOP='' PASS=0 FAIL=0
cleanup() { umount "$T/m" 2>/dev/null || true; [[ -n $LOOP ]] && losetup -d "$LOOP" 2>/dev/null; rm -rf "$T"; }
trap cleanup EXIT

# Copie de test : seuil FAT32 abaissé (10 Mo) pour forcer le découpage du WIM sans ISO de 5 Go.
sed -e 's/^readonly FAT32_MAX=4294967295 SWM_MB=3800/readonly FAT32_MAX=10485760 SWM_MB=12/' \
    -e "s|^export PATH=|export PATH=${TEST_PATH:+$TEST_PATH:}|" "$ROOT/linxfus" >"$T/linxfus"
chmod +x "$T/linxfus"; X=$T/linxfus

ok()   { echo "  ✓ $1"; PASS=$((PASS + 1)); }
ko()   { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }
check() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }
run()  { "$X" "$@" -d "$LOOP" -f -y >"$T/log" 2>&1; }
mnt()  { mkdir -p "$T/m"; mount -t vfat -o ro "${LOOP}p1" "$T/m" >/dev/null 2>&1; }
umnt() { umount "$T/m" 2>/dev/null || true; }

echo "== Préparation"
mkdir -p "$T/win/sources" "$T/win/efi/boot" "$T/pl" "$T/lin/boot" "$T/EFI/OC" "$T/EFI/BOOT"
head -c 30M /dev/urandom >"$T/pl/a.bin"; head -c 1M /dev/urandom >"$T/pl/b.bin"
wimlib-imagex capture "$T/pl" "$T/win/sources/install.wim" Test --compress=none >/dev/null
head -c 2M /dev/urandom >"$T/win/sources/boot.wim"
echo bootmgr >"$T/win/bootmgr"; echo efi >"$T/win/efi/boot/bootx64.efi"; echo setup >"$T/win/setup.exe"
xorriso -as mkisofs -quiet -J -R -V CCCOMA_X64FRE_FR-FR_DV9 -o "$T/win.iso" "$T/win" 2>/dev/null
head -c 5M /dev/urandom >"$T/lin/boot/vmlinuz"
xorriso -as mkisofs -quiet -J -R -V LINUX_LIVE -o "$T/lin.iso" "$T/lin" 2>/dev/null
cp "$T/lin.iso" "$T/nonhybrid.iso"; printf '\x55\xaa' | dd of="$T/lin.iso" bs=1 seek=510 conv=notrunc status=none
head -c 20M /dev/urandom >"$T/rpi.img"; xz -T0 -1 -k "$T/rpi.img"
head -c 3M /dev/urandom >"$T/BaseSystem.dmg"; head -c 2K /dev/urandom >"$T/BaseSystem.chunklist"
echo oc >"$T/EFI/OC/OpenCore.efi"; echo b >"$T/EFI/BOOT/BOOTx64.efi"
truncate -s 256M "$T/usb.img"; LOOP=$(losetup -fP --show "$T/usb.img")

echo "== Windows MBR + découpage WIM + bypass Win11"
check "exécution" 'run -i "$T/win.iso" --win11-bypass'
check "table MBR"           'parted -s "$LOOP" print | grep -q "Partition Table: msdos"'
mnt
check "install.wim absent"  '[[ ! -e $T/m/sources/install.wim ]]'
check "install*.swm créés"  '[[ -e $T/m/sources/install.swm && -e $T/m/sources/install2.swm ]]'
check "boot.wim intact"     'cmp -s "$T/win/sources/boot.wim" "$T/m/sources/boot.wim"'
check "autounattend.xml"    'grep -q BypassTPMCheck "$T/m/autounattend.xml"'
if grep -q "Démarrage BIOS (Legacy/CSM) installé" "$T/log"; then
  check "grub.cfg → bootmgr" 'grep -q "ntldr /bootmgr" "$T"/m/grub*/grub.cfg'
  check "GRUB dans le MBR"   'head -c 512 "$LOOP" | grep -aq GRUB'
elif [[ ${REQUIRE_BIOS:-0} == 1 ]]; then ko "chargeur BIOS installé"; grep -i grub "$T/log" || true
else echo "  - chargeur BIOS non testable ici"; fi
umnt

echo "== Windows GPT"
check "exécution"   'run -i "$T/win.iso" -s gpt'
check "table GPT"   'parted -s "$LOOP" print | grep -q "Partition Table: gpt"'

echo "== Linux / images brutes"
check "ISO hybride + -V"        'run -i "$T/lin.iso" -V && grep -q "Vérification OK" "$T/log"'
check "img.xz + -V"             'run -i "$T/rpi.img.xz" -V && grep -q "Vérification OK" "$T/log"'
check "contenu identique"       'cmp -s -n $((20 << 20)) "$T/rpi.img" "$LOOP"'
check "ISO non hybride signalée" 'run -i "$T/nonhybrid.iso" && grep -q isohybride "$T/log"'

echo "== macOS OpenCore"
check "exécution" 'run -i "$T/BaseSystem.dmg" --mac-mode opencore --efi "$T/EFI"'
mnt
check "dmg + chunklist" '[[ -s $T/m/com.apple.recovery.boot/BaseSystem.dmg && -s $T/m/com.apple.recovery.boot/BaseSystem.chunklist ]]'
check "EFI copié"       '[[ -s $T/m/EFI/OC/OpenCore.efi ]]'
umnt

echo "== Garde-fous"
dd if="$T/rpi.img" of="$LOOP" bs=4M oflag=direct status=none
check "DMG invalide refusé"         '! run -i "$T/BaseSystem.dmg" && grep -q "dmg2img ne sait pas" "$T/log"'
check "… sans effacer la clé"       'cmp -s -n $((20 << 20)) "$T/rpi.img" "$LOOP"'
check "SHA-256 faux"                '! run -i "$T/rpi.img" --sha256 "$(printf "0%.0s" {1..64})"'
check "SHA-256 mal formé"           '! run -i "$T/rpi.img" --sha256 abc'
check "version macOS inconnue"      '! run --mac-recovery windows95'
check "partition refusée"           '! "$X" -i "$T/rpi.img" -d "${LOOP}p1" -f -y >/dev/null 2>&1'
check "loop sans --force refusé"    '! "$X" -i "$T/rpi.img" -d "$LOOP" -y >/dev/null 2>&1'
check "sans terminal ni --yes"      '! "$X" -i "$T/rpi.img" -d "$LOOP" -f </dev/null >/dev/null 2>&1'
check "option sans valeur"          '! "$X" -i >/dev/null 2>&1'
check "--help"                      '"$X" --help | grep -q Usage'

echo; echo "Résultat : $PASS OK, $FAIL échec(s)"
((FAIL == 0))
