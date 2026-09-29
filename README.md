# Free Sprint Out of Combat

A Fallout 4 mod: sprinting costs no Action Points while you are out of combat, and AP keep regenerating
while you sprint, as if you were standing still. In combat sprinting works as usual.

MCM settings (all off by default):

- **Free sprint in combat too** - sprinting costs no AP in combat as well.
- **Free sprint in power armor** - the same in power armor. When off, power armor sprints as usual.
- **Economical fusion core drain** - sprinting in power armor drains the fusion core as if you covered the
  same distance at a normal run.

Without MCM the settings are globals: `set FSOC_InCombat to 1`, `set FSOC_PowerArmorAP to 1`,
`set FSOC_PowerArmorCore to 1`.

Русское описание, устройство и сборка - [README.ru.md](README.ru.md).

## How it works

The numbers below come from disassembling `Fallout4.exe` 1.10.163 with its PDB (`Fallout4.pdb`).

- The sprint drain (`Actor::UpdateSprinting`) is `12 * (1.05 - 0.05 * Endurance)` AP per second in vanilla,
  passed through the perk entry point **Mod Sprint AP Drain Rate** (EP 96) and then subtracted from AP
  every frame.
- The engine does **not** regenerate AP while you sprint at all (`Actor::ShouldRestoreActionPoints`), even
  when the sprint costs nothing. So the mod does not just zero the drain: a hidden perk multiplies it by a
  negative factor, `-(standing AP regen) / (vanilla sprint drain)`. The engine then restores AP every
  frame at the standing rate, smoothly; the damage modifier is clamped at zero, so AP never exceed the
  maximum. The Papyrus script `papyrus/FSOC/Main.psc` recalculates the factor about once a second
  (regen = `ActionPointsRate * 0.01 * max AP * ActionPointsRateMult * 0.01`, x0.75 in combat).
- The sprint flag stays set while you fly with a jetpack, so in power armor the script tracks jumps by the
  animation events the engine itself listens to (`JumpUp`/`JumpFall`, `JumpDown`/`PowerArmorHardLanding`).
  In the air sprinting is free but AP do not regenerate.
- In power armor the fusion core drains `0.05` per AP spent plus `0.05` per second of running (sprint
  counts as running). Free sprint removes the AP part, so the script brings the core drain to the chosen
  target: vanilla (sprint AP computed from the formula and the vanilla sprint perks) or economical (normal
  run over the same distance; power armor sprints 1.595 times faster than it runs).
- `PowerArmorBattery`, `ActionPointsRate` and `ActionPointsRateMult` are not records in `Fallout4.esm`: the
  engine registers them itself, and their FormIDs are `0x2BC + registration index` (`0x35C`, `0x2D8`,
  `0x359`).

Details and all formulas are in the docstring of `tools/gen_esp.py`.

## Requirements

- None beyond the base game. The plugin's only master is `Fallout4.esm`; no F4SE, no DLC.
- Optional: Mod Configuration Menu (needs F4SE) for the settings.

Tested on game version 1.10.163 (pre-Next-Gen).

## Building

```
python tools/gen_esp.py      # build\FreeSprintOutOfCombat.esp (reads Fallout4.esm from the installed game)
python tools/gen_mcm.py      # mod\MCM\Config\..., mod\Interface\Translations\*
"<game>\Papyrus Compiler\PapyrusCompiler.exe" papyrus -i="papyrus;<game>\Data\Scripts\Source\Base" ^
    -o="build\scripts" -f="Institute_Papyrus_Flags.flg" -all
python tools/deploy.py       # into the game (--remove to uninstall)
python tools/package.py 1.0.0
```

## License

The Unlicense - public domain. Made with Claude Code.
