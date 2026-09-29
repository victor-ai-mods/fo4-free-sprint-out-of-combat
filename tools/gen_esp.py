"""
Генератор `FreeSprintOutOfCombat.esp` (ESL, единственный мастер — Fallout4.esm).

    GLOB  FSOC_InCombat          — 1 = бег бесплатный и в бою (MCM, sourceType GlobalValue)
    GLOB  FSOC_PowerArmorAP      — 1 = бег бесплатный и в силовой броне (MCM)
    GLOB  FSOC_PowerArmorCore    — 1 = спринт в броне тратит ядро как обычный бег на то же расстояние (MCM)
                                   Эти три по умолчанию 0.
    GLOB  FSOC_Airborne          — 1 = игрок в силовой броне в воздухе (прыжок, ранец); ставит скрипт по событиям анимации
    AVIF  FSOC_RegenFactor       — множитель расхода на бег, при котором «расход» = -(восстановление AP стоя)
    AVIF  FSOC_RegenFactorCombat — то же в бою
    PERK  FSOC_Perk              — три записи EP 96 «Mod Sprint AP Drain Rate»; у всех общее условие
                                   (WornHasKeyword(isPowerArmorFrame) == 0 OR FSOC_PowerArmorAP == 1):
                                   0) не в бою, на земле:              Multiply Actor Value Mult FSOC_RegenFactor
                                   1) в бою и FSOC_InCombat, на земле: Multiply Actor Value Mult FSOC_RegenFactorCombat
                                   2) в воздухе (вне боя или FSOC_InCombat): Multiply Value x0
    QUST  FSOC_Quest             — Start Game Enabled, скрипт FSOC:Main (что он делает — ниже)

Как движок тратит бег, AP и ядро (Fallout4.exe 1.10.163, символы из Fallout4.pdb):
  Actor::UpdateSprinting — каждый кадр ModActorValue(Damage, AP, -drain), drain = CalcSprintingActionPoints * dt,
      пропущенный через HandleEntryPoint(96). Формула: (fSprintActionPointsWeightBase + fSprintActionPointsWeightMult
      * вес) * (fSprintActionPointsEndBase + fSprintActionPointsEndMult * Endurance) * fSprintActionPointsDrainMult;
      в Fallout4.esm это 12 * (1.05 - 0.05 * END) AP/с до перков. Ветка с fSprintBatteryDrainRate мёртвая.
  Actor::ShouldRestoreActionPoints — false, пока актёр бежит спринтом (кроме верховой езды): во время спринта AP
      не восстанавливаются ВООБЩЕ, даже при нулевом расходе. Поэтому «расход» делается отрицательным: движок сам
      каждый кадр прибавляет AP (плавно), а Actor::ModActorValue обрезает модификатор урона сверху нулём —
      выше максимума AP не поднимутся.
      Флаг спринта тот же, что у IsSprinting, и в полёте на ранце он остаётся — отсюда FSOC_Airborne.
  Actor::GetRestoreActorValueRate(ActionPoints) — ActionPointsRate * 0.01 * макс.AP * ActionPointsRateMult
      * 0.01, в бою ещё * fCombatActionPointsRegenRateMult (0.75).
  PowerArmor::HandleActionPointsModified — ядро -= fPowerArmorPowerDrainPerActionPoint * потраченные AP
      (только при уменьшении AP).
  PowerArmor::Update — пока Actor::IsRunning (спринт тоже считается), ядро -= fPowerArmorPowerDrainPerSecondRunning*dt.
  PowerArmor::DrainPlayerBattery — всё это умножается на AV PABatteryDamageRate игрока.

AV без записей в Fallout4.esm движок регистрирует сам (ActorValue::RegisterActorValues); их FormID =
0x2BC + номер регистрации (сверено с записями Health/ActionPoints/SpeedMult/HealRate/Rads):
PowerArmorBattery 0x35C, ActionPointsRate 0x2D8, ActionPointsRateMult 0x359. Скрипт берёт их через Game.GetForm.

Скрипт раз в секунду пересчитывает FSOC_RegenFactor* = -(восстановление AP стоя) / (ванильный расход на бег) и
держит FSOC_Airborne (только в броне: без неё прыжок короткий, AP в воздухе растут как в ванилле) по событиям
анимации JumpUp/JumpFall и JumpDown/PowerArmorHardLanding (их же слушает
движковый JumpAnimEventHandler). В силовой броне он же доводит расход ядра до нужного: «как обычный бег на то же
расстояние» = fPowerArmorPowerDrainPerSecondRunning * (спринт/бег) * dt (отношение скоростей — из MOVT
PowerArmor_Player_Default_MT), «как в ванилле» при бесплатных AP = бег + fPowerArmorPowerDrainPerActionPoint *
ванильный расход AP. Ванильный расход AP скрипт считает по формуле выше и перкам с EP 96 без условий из
Fallout4.esm — их таблицу собирает этот генератор (перки других модов не учитываются).

    python tools/gen_esp.py
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from esp_writer import (PROP_ARRAY_FLOAT, PROP_ARRAY_INT, PROP_ARRAY_OBJECT, PROP_FLOAT,  # noqa: E402
                        PROP_OBJECT, TES4_LIGHT, Record, Script, build_plugin, vmad, zstring)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.environ.get('FO4_PATH', r'D:\Games\Fallout 4')
PLUGIN_NAME = 'FreeSprintOutOfCombat.esp'
SCRIPT_MAIN = 'FSOC:Main'

# --- Fallout4.esm ---------------------------------------------------------------
KW_POWER_ARMOR_FRAME = 0x15503F
AV_ACTION_POINTS = 0x2D5
AV_ENDURANCE = 0x2C4
AV_PA_BATTERY_DAMAGE_RATE = 0x15A8B2
MOVT_PA_PLAYER_DEFAULT = 0x01ED65
SPED_RUN_FORWARD, SPED_SPRINT_FORWARD = 10, 11     # индексы float в SPED (wbDefinitionsFO4.pas, wbSPED)

# --- точка, функции, условия (wbDefinitionsFO4.pas) -------------------------------
EP_SPRINT_AP_DRAIN = 96
FN_MULTIPLY_VALUE = 3
FN_MUL_AV_MULT = 13
FN_MUL_1_PLUS_AV_MULT = 14
EPFT_FLOAT, EPFT_AVIF = 1, 8
CF_GET_GLOBAL_VALUE, CF_IS_IN_COMBAT, CF_WORN_HAS_KEYWORD = 74, 289, 682
OP_EQ = 0
FLAG_OR = 0x01

# --- свои FormID (ESL: 0x800..0xFFF) --------------------------------------------
BASE = 0x01000000
FID_QUEST = BASE | 0x800
FID_IN_COMBAT = BASE | 0x801
FID_PERK = BASE | 0x802
FID_PA_AP = BASE | 0x803
FID_PA_CORE = BASE | 0x804
FID_AIRBORNE = BASE | 0x805
FID_REGEN = BASE | 0x806
FID_REGEN_COMBAT = BASE | 0x807
NEXT_ID = 0x808


def ctda(func, comp, param1=0, op=OP_EQ, flags=0):
    """CTDA 32 байта: (оператор<<5 | флаги), сравнение, функция, параметр; run on = subject."""
    return struct.pack('<B3sfHHIIHHIi', (op << 5) | flags, b'\x00' * 3, float(comp), func, 0, param1,
                       0, 0, 0, 0, -1)


def load_esm():
    from esm import Plugin
    return Plugin(os.path.join(GAME, 'Data', 'Fallout4.esm'))


def sprint_to_run_ratio(esm):
    movt = next(r for r in esm.records(b'MOVT') if r.local_id == MOVT_PA_PLAYER_DEFAULT)
    sped = struct.unpack('<28f', movt.first(b'SPED'))
    ratio = sped[SPED_SPRINT_FORWARD] / sped[SPED_RUN_FORWARD]
    assert 1.2 < ratio < 2.0, 'странное отношение спринт/бег у %s: %r' % (movt.editor_id(), ratio)
    return ratio


def sprint_perks(esm):
    """
    Записи EP 96 без условий из перков Fallout4.esm: [(perk, функция, значение, AV или 0, EDID)].
    Записи с условиями пропускаются — их скрипт не может проверить.
    """
    avifs = {r.local_id for r in esm.records(b'AVIF')}
    out = []
    for r in esm.records(b'PERK'):
        subs = list(r.subrecords())
        for i, (tag, data) in enumerate(subs):
            if not (tag == b'DATA' and len(data) == 3 and i > 0 and subs[i - 1][0] == b'PRKE'
                    and data[0] == EP_SPRINT_AP_DRAIN):
                continue
            entry = {}
            j = i + 1
            while j < len(subs) and subs[j][0] != b'PRKF':
                entry.setdefault(subs[j][0], subs[j][1])
                j += 1
            if b'CTDA' in entry:
                print('  пропущен %s: запись EP 96 с условиями' % r.editor_id())
                continue
            func, eptype = data[1], entry[b'EPFT'][0]
            if func == FN_MULTIPLY_VALUE and eptype == EPFT_FLOAT:
                out.append((r.local_id, func, struct.unpack('<f', entry[b'EPFD'])[0], 0, r.editor_id()))
            elif func == FN_MUL_1_PLUS_AV_MULT and eptype == EPFT_AVIF:
                av, mult = struct.unpack('<If', entry[b'EPFD'])
                assert av in avifs, '%s: AV %#x не из Fallout4.esm' % (r.editor_id(), av)
                out.append((r.local_id, func, mult, av, r.editor_id()))
            else:
                raise ValueError('%s: неизвестная функция EP 96: %d / EPFT %d' % (r.editor_id(), func, eptype))
    return out


def glob(fid, edid, value):
    r = Record(b'GLOB', fid, edid)
    r.add(b'FLTV', struct.pack('<f', value))
    return r


def avif(fid, edid, desc):
    r = Record(b'AVIF', fid, edid)
    r.add(b'DESC', zstring(desc))
    r.add(b'NAM0', struct.pack('<f', 0.0))
    r.add(b'AVFL', struct.pack('<I', 0x2000))      # как у HC_IncomingDamageMult (см. No Safe Level)
    r.add(b'NAM1', struct.pack('<I', 8))           # Variable
    return r


def add_entry(perk, entry_id, func, conditions, av=None, value=0.0):
    perk.add(b'PRKE', struct.pack('<BBB', 2, 0, 0))
    perk.add(b'DATA', struct.pack('<BBB', EP_SPRINT_AP_DRAIN, func, 1))
    perk.add(b'PRKC', struct.pack('<B', 0))
    for c in conditions:
        perk.add(b'CTDA', c)
    if av is None:
        perk.add(b'EPFT', struct.pack('<B', EPFT_FLOAT))
        perk.add(b'EPFB', struct.pack('<H', entry_id))
        perk.add(b'EPFD', struct.pack('<f', value))
    else:
        perk.add(b'EPFT', struct.pack('<B', EPFT_AVIF))
        perk.add(b'EPFB', struct.pack('<H', entry_id))
        perk.add(b'EPFD', struct.pack('<If', av, 1.0))
    perk.add(b'PRKF', b'')


def build(ratio, perks):
    perk = Record(b'PERK', FID_PERK, 'FSOC_Perk')
    perk.add(b'FULL', zstring('Free Sprint Out of Combat'))
    perk.add(b'DESC', zstring(''))
    perk.add(b'DATA', bytes([0, 0, 1, 0, 1]))       # не играбельный, скрытый
    # Соседние условия с флагом OR связываются сильнее, чем AND: (A OR B) AND C AND ...
    not_pa = [ctda(CF_WORN_HAS_KEYWORD, 0.0, KW_POWER_ARMOR_FRAME, flags=FLAG_OR),
              ctda(CF_GET_GLOBAL_VALUE, 1.0, FID_PA_AP)]
    on_ground = ctda(CF_GET_GLOBAL_VALUE, 0.0, FID_AIRBORNE)
    add_entry(perk, 0, FN_MUL_AV_MULT, not_pa + [ctda(CF_IS_IN_COMBAT, 0.0), on_ground], av=FID_REGEN)
    add_entry(perk, 1, FN_MUL_AV_MULT,
              not_pa + [ctda(CF_IS_IN_COMBAT, 1.0), ctda(CF_GET_GLOBAL_VALUE, 1.0, FID_IN_COMBAT), on_ground],
              av=FID_REGEN_COMBAT)
    add_entry(perk, 2, FN_MULTIPLY_VALUE,
              not_pa + [ctda(CF_IS_IN_COMBAT, 0.0, flags=FLAG_OR), ctda(CF_GET_GLOBAL_VALUE, 1.0, FID_IN_COMBAT),
                        ctda(CF_GET_GLOBAL_VALUE, 1.0, FID_AIRBORNE)],
              value=0.0)

    quest = Record(b'QUST', FID_QUEST, 'FSOC_Quest')
    s = Script(SCRIPT_MAIN)
    for name, fid in [('FSOC_Perk', FID_PERK), ('FSOC_InCombat', FID_IN_COMBAT),
                      ('FSOC_PowerArmorAP', FID_PA_AP), ('FSOC_PowerArmorCore', FID_PA_CORE),
                      ('FSOC_Airborne', FID_AIRBORNE), ('FSOC_RegenFactor', FID_REGEN),
                      ('FSOC_RegenFactorCombat', FID_REGEN_COMBAT),
                      ('ActionPoints', AV_ACTION_POINTS), ('Endurance', AV_ENDURANCE),
                      ('PABatteryDamageRate', AV_PA_BATTERY_DAMAGE_RATE)]:
        s.prop(name, PROP_OBJECT, fid)
    s.prop('SprintToRunRatio', PROP_FLOAT, ratio)
    s.prop('SprintPerks', PROP_ARRAY_OBJECT, [p[0] for p in perks])
    s.prop('SprintPerkFunc', PROP_ARRAY_INT, [p[1] for p in perks])
    s.prop('SprintPerkValue', PROP_ARRAY_FLOAT, [p[2] for p in perks])
    s.prop('SprintPerkAV', PROP_ARRAY_OBJECT, [p[3] for p in perks])
    quest.add(b'VMAD', vmad([s]))
    quest.add(b'FULL', zstring('Free Sprint Out of Combat'))
    quest.add(b'DNAM', struct.pack('<HBBII', 0x0111, 0, 0x5E, 0, 0))   # Start Game Enabled | Run Once
    quest.add(b'NEXT', b'')
    quest.add(b'ANAM', struct.pack('<I', 0))

    globs = [glob(FID_IN_COMBAT, 'FSOC_InCombat', 0.0), glob(FID_PA_AP, 'FSOC_PowerArmorAP', 0.0),
             glob(FID_PA_CORE, 'FSOC_PowerArmorCore', 0.0), glob(FID_AIRBORNE, 'FSOC_Airborne', 0.0)]
    avifs = [avif(FID_REGEN, 'FSOC_RegenFactor', 'Free Sprint Out of Combat: sprint AP drain multiplier'),
             avif(FID_REGEN_COMBAT, 'FSOC_RegenFactorCombat',
                  'Free Sprint Out of Combat: sprint AP drain multiplier in combat')]
    return [(b'GLOB', globs), (b'AVIF', avifs), (b'PERK', [perk]), (b'QUST', [quest])]


def check(path):
    from esm import Plugin
    plugin = Plugin(path)
    assert plugin.masters == ['Fallout4.esm'], 'мастера: %r' % (plugin.masters,)
    counts = {sig.decode(): sum(1 for _ in plugin.records(sig)) for sig in (b'GLOB', b'AVIF', b'PERK', b'QUST')}
    assert counts == {'GLOB': 4, 'AVIF': 2, 'PERK': 1, 'QUST': 1}, counts
    perk = next(plugin.records(b'PERK'))
    entries = sum(1 for tag, _ in perk.subrecords() if tag == b'PRKE')
    assert entries == 3, entries
    print('  проверка: мастер один, записи %s, записей в перке %d' % (counts, entries))


def main():
    esm = load_esm()
    ratio = sprint_to_run_ratio(esm)
    perks = sprint_perks(esm)
    for p in perks:
        print('  перк EP 96: %-28s функция %2d значение %+.3f AV %#x' % (p[4], p[1], p[2], p[3]))
    out_path = os.path.join(ROOT, 'build', PLUGIN_NAME)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    blob = build_plugin(['Fallout4.esm'], build(ratio, perks), NEXT_ID, flags=TES4_LIGHT)
    with open(out_path, 'wb') as f:
        f.write(blob)
    print('%s: %d байт, спринт/бег в броне %.4f' % (out_path, len(blob), ratio))
    check(out_path)


if __name__ == '__main__':
    main()
