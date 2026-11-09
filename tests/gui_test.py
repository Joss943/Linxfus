#!/usr/bin/python3
"""Test de bout en bout de l'interface (root, sous Xvfb) : xvfb-run sudo tests/gui_test.py [dossier_captures]

Pilote la vraie fenêtre GTK : choix d'image, options, écriture sur un loop device, annulation.
TEST_PATH (optionnel) : dossier préfixé au PATH du moteur (bac à sable sans vfat noyau).
"""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import GLib, Graphene, Gtk  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
T = tempfile.mkdtemp()
sh = lambda *a, **k: subprocess.run(*a, shell=True, check=True, **k)  # noqa: E731

# Copie de test : seuil FAT32 abaissé (10 Mo) pour forcer le découpage du WIM.
src = open(os.path.join(ROOT, 'linxfus')).read()
src = src.replace('readonly FAT32_MAX=4294967295 SWM_MB=3800', 'readonly FAT32_MAX=10485760 SWM_MB=12')
if os.environ.get('TEST_PATH'):
    src = src.replace('export PATH=', f'export PATH={os.environ["TEST_PATH"]}:', 1)
open(f'{T}/linxfus', 'w').write(src)
shutil.copy(os.path.join(ROOT, 'linxfus-gui'), f'{T}/linxfus-gui')
os.chmod(f'{T}/linxfus', 0o755)
loader = importlib.machinery.SourceFileLoader('gui', f'{T}/linxfus-gui')
gui = importlib.util.module_from_spec(importlib.util.spec_from_loader('gui', loader))
loader.exec_module(gui)

# Images de test
os.makedirs(f'{T}/win/sources')
os.makedirs(f'{T}/win/efi/boot')
os.makedirs(f'{T}/pl')
sh(f'head -c 30M /dev/urandom > {T}/pl/a.bin && head -c 1M /dev/urandom > {T}/pl/b.bin')
sh(f'wimlib-imagex capture {T}/pl {T}/win/sources/install.wim Test --compress=none >/dev/null')
sh(f'head -c 2M /dev/urandom > {T}/win/sources/boot.wim; echo b > {T}/win/bootmgr; echo e > {T}/win/efi/boot/bootx64.efi')
if shutil.which('modprobe'):
    subprocess.run(['modprobe', '-q', 'udf'], stderr=subprocess.DEVNULL)   # module noyau chargé à la demande
udf = 'udf' in open('/proc/filesystems').read()
if udf:   # vraie ISO Microsoft : UDF
    sh(f'genisoimage -quiet -udf -iso-level 3 -J -V CCCOMA_X64FRE_FR-FR_DV9 -o {T}/win.iso {T}/win 2>/dev/null')
else:     # noyau sans UDF : ISO9660, type forcé plus bas
    sh(f'xorriso -as mkisofs -quiet -J -R -V CCCOMA_X64FRE_FR-FR_DV9 -o {T}/win.iso {T}/win 2>/dev/null')
sh(f'head -c 20M /dev/urandom > {T}/rpi.img && xz -T0 -1 -k {T}/rpi.img')
sh(f'head -c 200M /dev/urandom | xz -T1 -0 > {T}/big.img.xz')
sh(f'truncate -s 256M {T}/usb.img')
LOOP = subprocess.run(['losetup', '-fP', '--show', f'{T}/usb.img'], capture_output=True, text=True,
                      check=True).stdout.strip()

results, steps = [], []


def check(name, cond):
    results.append((name, bool(cond)))
    print(('  ✓ ' if cond else '  ✗ ') + name, flush=True)


def shot(win, name):
    if not SHOTS:
        return
    w, h = win.get_width(), win.get_height()
    snap = Gtk.Snapshot()
    Gtk.WidgetPaintable.new(win).snapshot(snap, w, h)
    node = snap.to_node()
    if node:
        tex = win.get_native().get_renderer().render_texture(node, Graphene.Rect().init(0, 0, w, h))
        tex.save_to_png(os.path.join(SHOTS, f'{name}.png'))


def main(app):
    win = app.win
    win.refresh_devices = lambda force=False: True          # liste figée sur le loop device
    win.devices = [(LOOP, 268435456, 'Clé de test')]
    gui.set_items(win.dev_dd, ['Clé de test (%s) [268 Mo]' % LOOP])
    real_build = win.build_args
    win.build_args = lambda: real_build() + ['-f']
    done = {}
    orig_done = win.on_done

    def on_done(rc):
        done['rc'] = rc
        return orig_done(rc)
    win.on_done = on_done

    def wait_done(then):
        def poll():
            if 'rc' in done:
                then(done.pop('rc'))
                return False
            return True
        GLib.timeout_add(200, poll)

    def step_windows():
        win.update_ui()
        check('démarrage : DÉMARRER inactif sans image', not win.start_btn.get_sensitive())
        shot(win, '1-accueil')
        win.set_image(f'{T}/win.iso')
        if not udf:
            win.img_kind = 'windows'
            win.update_ui()
        check('ISO Windows détectée' if udf else 'ISO Windows (type forcé)', win.kind() == 'windows')
        check('option d\'image visible', win.opt_field.get_visible())
        win.wue = {'bypass': True, 'no_online': True, 'user_on': True, 'user': 'Jean Test',
                   'no_data': True, 'no_bitlocker': False}
        seen = []
        win.ask_wue(lambda: seen.append(1))
        dlg = win.wue_win
        dlg.user_ent.set_text('a/b')
        dlg.ok_btn.emit('clicked')
        check('options Windows : nom de compte invalide refusé', not seen and dlg.user_ent.has_css_class('error'))
        dlg.user_ent.set_text('Jean Test')
        dlg.checks['no_bitlocker'].set_active(True)
        if SHOTS:
            GLib.timeout_add(350, lambda: shot(dlg, '2b-options-windows') or False)
            GLib.timeout_add(450, lambda: dlg.ok_btn.emit('clicked') or False)
        else:
            dlg.ok_btn.emit('clicked')
        check('nom de volume = label ISO', win.label_ent.get_text() == 'CCCOMA_X64F')
        check('DÉMARRER actif', win.start_btn.get_sensitive())
        GLib.timeout_add(700, lambda: step_windows_run() or False)

    def step_windows_run():
        shot(win, '2-windows')
        args = win.build_args()
        check('options Windows : dialogue validé', win.wue['no_bitlocker'] and win.wue['user'] == 'Jean Test')
        check('arguments Windows', all(a in args for a in (
            '-s', '--win11-bypass', '--no-online-account', '--no-data-collection', '--no-bitlocker',
            '--local-account', 'Jean Test')))
        win.run(args)
        GLib.timeout_add(400, lambda: shot(win, '3-en-cours') or False)
        wait_done(after_windows)

    def after_windows(rc):
        check('écriture Windows : code 0', rc == 0)
        check('barre « PRÊT »', win.bar_lab.get_label() == 'PRÊT' and win.bar.get_fraction() == 1)
        log = win.log_buf.get_text(win.log_buf.get_start_iter(), win.log_buf.get_end_iter(), False)
        check('découpage WIM journalisé', 'découpage' in log)
        GLib.timeout_add(500, lambda: step_macos() or False)

    def step_macos():
        shot(win, '4-pret')
        # macOS : téléchargement (UI seulement)
        win.boot_dd.set_selected(1)
        check('macOS : liste des versions', win.opt_dd.get_model().get_n_items() == len(gui.MACOS))
        win.target_dd.set_selected(1)
        check('Hackintosh : dossier EFI proposé', win.efi_field.get_visible())
        check('Hackintosh : FAT32', win.fs_dd.get_model().get_string(0) == 'FAT32')
        check('Hackintosh : nom MACRECOVERY', win.label_ent.get_text() == 'MACRECOVERY')
        win.target_dd.set_selected(0)
        check('Mac Intel récent : avertissement', win.hint.get_visible())
        win.target_dd.set_selected(1)
        GLib.timeout_add(500, lambda: step_linux() or False)

    def step_linux():
        shot(win, '5-macos')
        win.boot_dd.set_selected(0)
        # Linux : image compressée + vérification
        win.set_image(f'{T}/rpi.img.xz')
        check('image Linux', win.kind() == 'linux' and not win.scheme_dd.get_sensitive())
        win.verify_chk.set_active(True)
        win.run(win.build_args())
        wait_done(after_linux)

    def after_linux(rc):
        log = win.log_buf.get_text(win.log_buf.get_start_iter(), win.log_buf.get_end_iter(), False)
        check('écriture Linux + vérification : code 0', rc == 0 and 'Vérification OK' in log)
        r = subprocess.run(['cmp', '-n', str(20 << 20), f'{T}/rpi.img', LOOP])
        check('contenu de la clé identique', r.returncode == 0)
        # Formatage simple (non amorçable)
        win.boot_dd.set_selected(2)
        names = [f[0] for f in win.fs_avail]
        check('formatage : systèmes de fichiers proposés', win.kind() == 'format' and 'ext4' in names
              and win.label_ent.get_sensitive() and not win.sel_btn.get_sensitive())
        win.fs_dd.set_selected(names.index('ext4'))
        win.scheme_dd.set_selected(1)
        win.label_ent.set_text('DONNEES')
        args = win.build_args()
        check('formatage : arguments', args[2:6] == ['--format', 'ext4', '-s', 'gpt'] and 'DONNEES' in args)
        GLib.timeout_add(400, lambda: (shot(win, '6-formatage'), win.run(args)) and False)
        wait_done(after_format)

    def after_format(rc):
        out = subprocess.run(['blkid', '-p', '-o', 'export', LOOP + 'p1'], capture_output=True, text=True).stdout
        check('formatage ext4 + nom de volume', rc == 0 and 'TYPE=ext4' in out and 'LABEL=DONNEES' in out)
        win.boot_dd.set_selected(0)
        # Annulation en cours d'écriture
        win.verify_chk.set_active(False)
        win.set_image(f'{T}/big.img.xz')
        win.run(win.build_args())

        def cancel():
            if 'Écriture' in win.bar_lab.get_label():
                win.cancel(1)
                return False
            return 'rc' not in done
        GLib.timeout_add(50, cancel)
        wait_done(after_cancel)

    def after_cancel(rc):
        check('annulation : moteur arrêté', rc != 0 and win.proc is None)
        check('annulation : barre « ANNULÉ »', win.bar_lab.get_label() == 'ANNULÉ')
        r = subprocess.run(f'ps -eo args | grep -c "[d]d of={LOOP}"', shell=True, capture_output=True, text=True)
        check('annulation : plus de dd en cours', r.stdout.strip() == '0')
        check('annulation : dossier de travail nettoyé', not any(
            n.startswith('linxfus.') for n in os.listdir('/var/tmp')))
        app.quit()

    GLib.timeout_add(500, lambda: step_windows() or False)


app = gui.App()
app.connect('activate', lambda a: GLib.idle_add(lambda: main(a) or False))
GLib.timeout_add_seconds(240, lambda: (print('  ✗ délai dépassé'), results.append(('délai', False)), app.quit()))
try:
    app.run([])
finally:
    subprocess.run(['losetup', '-d', LOOP])
    shutil.rmtree(T, ignore_errors=True)
ko = [n for n, ok in results if not ok]
print(f'\nRésultat interface : {len(results) - len(ko)} OK, {len(ko)} échec(s)')
sys.exit(1 if ko else 0)
