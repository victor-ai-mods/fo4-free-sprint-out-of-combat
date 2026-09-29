"""
Раскладка мода по игре.

  python tools/deploy.py            — FreeSprintOutOfCombat.esp, FSOC\\Main.pex, MCM, переводы; включить
  python tools/deploy.py --remove   — снять плагин и убрать его файлы

`Plugins.txt` в этой установке живёт в ДВУХ местах (игра читает
`%LOCALAPPDATA%\\Fallout4\\Plugins.txt`) — правятся оба. Всё, что перезаписывается,
сначала уезжает в `<игра>\\Backup`.
"""

import argparse
import datetime
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.environ.get('FO4_PATH', r'D:\Games\Fallout 4')
DATA = os.path.join(GAME, 'Data')
PLUGIN = 'FreeSprintOutOfCombat.esp'
SCRIPTS = [os.path.join('FSOC', 'Main.pex')]
MOD_FILES = os.path.join(ROOT, 'mod')           # пути внутри — как от Data

PLUGIN_LISTS = [
    os.path.join(os.environ['LOCALAPPDATA'], 'Fallout4', 'Plugins.txt'),
    os.path.join(GAME, 'fallout4', 'Plugins.txt'),
]


def backup(path):
    if not os.path.exists(path):
        return None
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    target_dir = os.path.join(GAME, 'Backup')
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, '%s.%s.bak' % (os.path.basename(path), stamp))
    shutil.copy2(path, target)
    return target


def copy(src, dst):
    saved = backup(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print('  %s%s' % (dst, ('  (старый -> %s)' % os.path.basename(saved)) if saved else ''))


def set_enabled(enabled):
    for path in PLUGIN_LISTS:
        if not os.path.exists(path):
            print('  нет %s — пропущено' % path)
            continue
        with open(path, encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
        kept = [ln for ln in lines if ln.lstrip('*').strip().lower() != PLUGIN.lower()]
        if enabled:
            kept.append('*' + PLUGIN)
        if kept != lines:
            backup(path)
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n'.join(kept) + '\n')
        print('  %s: %s' % (path, 'включён' if enabled else 'выключен'))


def mod_files():
    out = []
    for base, _, names in os.walk(MOD_FILES):
        for name in names:
            out.append(os.path.relpath(os.path.join(base, name), MOD_FILES))
    return sorted(out)


def script_paths():
    return [(os.path.join(ROOT, 'build', 'scripts', n), os.path.join(DATA, 'Scripts', n)) for n in SCRIPTS]


def install():
    print('Файлы:')
    copy(os.path.join(ROOT, 'build', PLUGIN), os.path.join(DATA, PLUGIN))
    for src, dst in script_paths():
        copy(src, dst)
    for rel in mod_files():
        copy(os.path.join(MOD_FILES, rel), os.path.join(DATA, rel))
    print('Порядок загрузки:')
    set_enabled(True)


def remove():
    print('Порядок загрузки:')
    set_enabled(False)
    print('Файлы:')
    paths = [os.path.join(DATA, PLUGIN)] + [dst for _, dst in script_paths()]
    paths += [os.path.join(DATA, rel) for rel in mod_files()]
    for path in paths:
        if os.path.exists(path):
            backup(path)
            os.remove(path)
            print('  удалён %s' % path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--remove', action='store_true')
    args = ap.parse_args()
    if args.remove:
        remove()
    else:
        install()
        print('\nesp и .pex подхватываются только при запуске игры.')


if __name__ == '__main__':
    main()
