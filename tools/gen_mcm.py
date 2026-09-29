"""
Генератор MCM и переводов Free Sprint Out of Combat.

Выход (в mod/, откуда их раскладывает tools/deploy.py):
    MCM/Config/FreeSprintOutOfCombat/config.json            — страница, тексты токенами $FSOC_*
    Interface/Translations/FreeSprintOutOfCombat_{en,ru}.txt — UTF-16 LE с BOM, TAB, CRLF

Три настройки — switcher прямо на глобальные переменные (sourceType GlobalValue — так же делают SCM
и NPCs Use Items): FSOC_InCombat «бесплатно и в бою», FSOC_PowerArmorAP «бесплатно в силовой броне»,
FSOC_PowerArmorCore «ядро при спринте как при обычном беге». Значения живут в сохранении; перк читает их
при каждом расчёте расхода, скрипт FSOC:Main — раз в 0.25-0.5 с.

    python tools/gen_mcm.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'mod')
MOD = 'FreeSprintOutOfCombat'
PLUGIN = 'FreeSprintOutOfCombat.esp'
IN_COMBAT_GLOBAL = PLUGIN + '|801'
PA_AP_GLOBAL = PLUGIN + '|803'
PA_CORE_GLOBAL = PLUGIN + '|804'

STRINGS = {
    'en': {
        'MOD_NAME': 'Free Sprint Out of Combat',
        'ABOUT': 'Sprinting costs no Action Points while you are out of combat, '
                 'and Action Points keep regenerating as if you were standing still.',
        'SEC_MAIN': 'Settings',
        'IN_COMBAT': 'Free sprint in combat too',
        'IN_COMBAT_HELP': 'When on, sprinting costs no AP in combat as well.',
        'SEC_POWER_ARMOR': 'Power armor',
        'PA_AP': 'Free sprint in power armor',
        'PA_AP_HELP': 'When on, sprinting in power armor costs no AP either. '
                      'When off, sprinting in power armor costs AP as usual.',
        'PA_CORE': 'Economical fusion core drain',
        'PA_CORE_HELP': 'When on, sprinting in power armor drains the fusion core as if you covered the same '
                        'distance at a normal run. When off, the core drains as usual.',
    },
    'ru': {
        'MOD_NAME': 'Free Sprint Out of Combat',
        'ABOUT': 'Бег вне боя не тратит очки действия, а ОД продолжают восстанавливаться, как будто вы стоите.',
        'SEC_MAIN': 'Настройки',
        'IN_COMBAT': 'Бесплатный бег и в бою',
        'IN_COMBAT_HELP': 'Если включено, бег не тратит ОД и в бою.',
        'SEC_POWER_ARMOR': 'Силовая броня',
        'PA_AP': 'Бесплатный бег в силовой броне',
        'PA_AP_HELP': 'Если включено, бег в силовой броне тоже не тратит ОД. '
                      'Если выключено, бег в броне тратит ОД как обычно.',
        'PA_CORE': 'Экономный расход ядерного блока',
        'PA_CORE_HELP': 'Если включено, бег в силовой броне расходует ядерный блок так, будто то же расстояние '
                        'пройдено обычным ходом. Если выключено, блок расходуется как обычно.',
    },
}


def t(key):
    return '$FSOC_' + key


def config():
    return {
        'modName': MOD,
        'displayName': t('MOD_NAME'),
        'minMcmVersion': 2,
        'pluginRequirements': [PLUGIN],
        'content': [
            {'type': 'text', 'text': t('ABOUT')},
            {'type': 'spacer'},
            {'type': 'section', 'text': t('SEC_MAIN')},
            {'type': 'switcher', 'text': t('IN_COMBAT'), 'help': t('IN_COMBAT_HELP'),
             'valueOptions': {'sourceType': 'GlobalValue', 'sourceForm': IN_COMBAT_GLOBAL}},
            {'type': 'spacer'},
            {'type': 'section', 'text': t('SEC_POWER_ARMOR')},
            {'type': 'switcher', 'text': t('PA_AP'), 'help': t('PA_AP_HELP'),
             'valueOptions': {'sourceType': 'GlobalValue', 'sourceForm': PA_AP_GLOBAL}},
            {'type': 'switcher', 'text': t('PA_CORE'), 'help': t('PA_CORE_HELP'),
             'valueOptions': {'sourceType': 'GlobalValue', 'sourceForm': PA_CORE_GLOBAL}},
        ],
    }


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write('\n')


def main():
    cfg_dir = os.path.join(OUT, 'MCM', 'Config', MOD)
    write_json(os.path.join(cfg_dir, 'config.json'), config())
    keys = set(STRINGS['en'])
    tr_dir = os.path.join(OUT, 'Interface', 'Translations')
    os.makedirs(tr_dir, exist_ok=True)
    for lang, table in STRINGS.items():
        assert set(table) == keys, '%s: ключи не совпадают с en: %s' % (lang, keys ^ set(table))
        for k, v in table.items():
            assert '\t' not in v and '\n' not in v, (lang, k)
            if k.endswith('_HELP') and len(v) > 165:
                print('  ! %s %s: подсказка %d символов (> 165 — мелкий шрифт)' % (lang, k, len(v)))
        text = ''.join('%s\t%s\r\n' % (t(k), v) for k, v in table.items())
        with open(os.path.join(tr_dir, '%s_%s.txt' % (MOD, lang)), 'wb') as f:
            f.write(b'\xff\xfe' + text.encode('utf-16-le'))
    print('MCM: %s, переводы: %s' % (os.path.relpath(cfg_dir, ROOT), ', '.join(STRINGS)))


if __name__ == '__main__':
    main()
