Scriptname FSOC:Main extends Quest
{Free Sprint Out of Combat.
Gives the player the hidden perk that makes sprinting free (the perk itself decides when). The engine never
regenerates AP during a sprint, so the perk turns the sprint drain negative: the engine then restores AP every
frame by itself. This script only keeps the numbers the perk needs up to date:
- FSOC_RegenFactor* = -(standing AP regen) / (vanilla sprint drain), recalculated about once a second;
- FSOC_Airborne from jump animation events, power armor only (no regen while flying with a jetpack);
- in power armor, the fusion core drain correction (see tools/gen_esp.py for the engine formulas).}

Perk Property FSOC_Perk Auto Const Mandatory
GlobalVariable Property FSOC_InCombat Auto Const Mandatory
GlobalVariable Property FSOC_PowerArmorAP Auto Const Mandatory
GlobalVariable Property FSOC_PowerArmorCore Auto Const Mandatory
GlobalVariable Property FSOC_Airborne Auto Const Mandatory
ActorValue Property FSOC_RegenFactor Auto Const Mandatory
ActorValue Property FSOC_RegenFactorCombat Auto Const Mandatory
ActorValue Property ActionPoints Auto Const Mandatory
ActorValue Property Endurance Auto Const Mandatory
ActorValue Property PABatteryDamageRate Auto Const Mandatory
{Rate multiplier the engine applies to every battery drain (PowerArmor::DrainPlayerBattery).}
Float Property SprintToRunRatio Auto Const Mandatory
{Sprint / run speed of PowerArmor_Player_Default_MT, filled by tools/gen_esp.py.}
Perk[] Property SprintPerks Auto Const Mandatory
{Fallout4.esm perks with an unconditional "Mod Sprint AP Drain Rate" entry.}
Int[] Property SprintPerkFunc Auto Const Mandatory
{3 = multiply by SprintPerkValue, 14 = multiply by 1 + SprintPerkAV * SprintPerkValue.}
Float[] Property SprintPerkValue Auto Const Mandatory
ActorValue[] Property SprintPerkAV Auto Const Mandatory

; Actor values the engine registers itself (not stored in Fallout4.esm): FormID = 0x2BC + index.
Int Property BATTERY_FORMID = 0x35C AutoReadOnly Hidden
Int Property AP_RATE_FORMID = 0x2D8 AutoReadOnly Hidden
Int Property AP_RATE_MULT_FORMID = 0x359 AutoReadOnly Hidden
Int Property FUNC_MULTIPLY = 3 AutoReadOnly Hidden
Int Property FUNC_MULTIPLY_1_PLUS_AV = 14 AutoReadOnly Hidden
Float Property IDLE_INTERVAL = 1.0 AutoReadOnly Hidden
Float Property CORE_INTERVAL = 0.25 AutoReadOnly Hidden
Float Property MAX_STEP = 1.0 AutoReadOnly Hidden
Float Property AIRBORNE_TIMEOUT = 20.0 AutoReadOnly Hidden
{Safety net: the flag is dropped if no landing event arrives for this long.}

Actor Player
ActorValue Battery
ActorValue APRate
ActorValue APRateMult
Float RunDrainPerSecond
Float DrainPerAP
Float CombatRegenMult
Float SprintDrainMult
Float SprintWeightBase
Float SprintEndBase
Float SprintEndMult
Float LastTick
Float LastAP
Float MaxAP
Float AirborneSince
Bool WasInPowerArmor
Bool EventsRegistered

Event OnQuestInit()
    Setup()
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Setup()
EndEvent

Function Setup()
    Player = Game.GetPlayer()
    RegisterForRemoteEvent(Player, "OnPlayerLoadGame")
    If !Player.HasPerk(FSOC_Perk)
        Player.AddPerk(FSOC_Perk)
    EndIf
    Battery = Game.GetForm(BATTERY_FORMID) as ActorValue
    APRate = Game.GetForm(AP_RATE_FORMID) as ActorValue
    APRateMult = Game.GetForm(AP_RATE_MULT_FORMID) as ActorValue
    RunDrainPerSecond = Game.GetGameSettingFloat("fPowerArmorPowerDrainPerSecondRunning")
    DrainPerAP = Game.GetGameSettingFloat("fPowerArmorPowerDrainPerActionPoint")
    CombatRegenMult = Game.GetGameSettingFloat("fCombatActionPointsRegenRateMult")
    SprintDrainMult = Game.GetGameSettingFloat("fSprintActionPointsDrainMult")
    SprintWeightBase = Game.GetGameSettingFloat("fSprintActionPointsWeightBase")
    SprintEndBase = Game.GetGameSettingFloat("fSprintActionPointsEndBase")
    SprintEndMult = Game.GetGameSettingFloat("fSprintActionPointsEndMult")
    SetAirborne(false)
    WasInPowerArmor = Player.IsInPowerArmor()
    RegisterJumpEvents()
    UpdateRegenFactors()
    Debug.Trace("FSOC: setup battery=" + Battery + " apRate=" + APRate + " apRateMult=" + APRateMult \
        + " sprintAP=" + VanillaSprintAP() + " maxAP=" + MaxAP + " factor=" + Player.GetValue(FSOC_RegenFactor) \
        + " jumpEvents=" + EventsRegistered)
    LastTick = 0.0
    LastAP = Player.GetValue(ActionPoints)
    StartTimer(IDLE_INTERVAL)
EndFunction

; ---- airborne flag -------------------------------------------------------------------------------------

; The same events the engine's JumpAnimEventHandler listens to. Only power armor needs the flag (the jetpack):
; outside it a jump is short and AP regenerate in the air as usual. The behavior graph changes when the player
; enters or leaves power armor, so registration is renewed then.
Function RegisterJumpEvents()
    If WasInPowerArmor
        Bool ok = RegisterForAnimationEvent(Player, "JumpUp")
        ok = RegisterForAnimationEvent(Player, "JumpFall") && ok
        ok = RegisterForAnimationEvent(Player, "JumpDown") && ok
        ok = RegisterForAnimationEvent(Player, "PowerArmorHardLanding") && ok
        EventsRegistered = ok
    Else
        UnregisterForAnimationEvent(Player, "JumpUp")
        UnregisterForAnimationEvent(Player, "JumpFall")
        UnregisterForAnimationEvent(Player, "JumpDown")
        UnregisterForAnimationEvent(Player, "PowerArmorHardLanding")
        EventsRegistered = true
    EndIf
EndFunction

Event OnAnimationEvent(ObjectReference akSource, string asEventName)
    If !WasInPowerArmor
        Return
    EndIf
    If asEventName == "JumpUp" || asEventName == "JumpFall"
        SetAirborne(true)
    ElseIf asEventName == "JumpDown" || asEventName == "PowerArmorHardLanding"
        SetAirborne(false)
    EndIf
EndEvent

Function SetAirborne(Bool airborne)
    If airborne
        If FSOC_Airborne.GetValue() != 1.0
            AirborneSince = Utility.GetCurrentRealTime()
            FSOC_Airborne.SetValue(1.0)
            Debug.Trace("FSOC: airborne")
        EndIf
    ElseIf FSOC_Airborne.GetValue() != 0.0
        FSOC_Airborne.SetValue(0.0)
        Debug.Trace("FSOC: landed")
    EndIf
EndFunction

; ---- periodic work ---------------------------------------------------------------------------------------

Event OnTimer(int aiTimerID)
    Float now = Utility.GetCurrentRealTime()
    Float dt = 0.0
    If LastTick > 0.0
        dt = Math.Min(now - LastTick, MAX_STEP)
    EndIf
    LastTick = now

    Bool inPowerArmor = Player.IsInPowerArmor()
    If inPowerArmor != WasInPowerArmor || !EventsRegistered
        WasInPowerArmor = inPowerArmor
        SetAirborne(false)
        RegisterJumpEvents()
    ElseIf FSOC_Airborne.GetValue() == 1.0 && now - AirborneSince > AIRBORNE_TIMEOUT
        SetAirborne(false)
    EndIf

    UpdateRegenFactors()

    Float ap = Player.GetValue(ActionPoints)
    Bool coreWork = false
    If inPowerArmor && Player.IsSprinting() && FSOC_Airborne.GetValue() == 0.0
        coreWork = true
        If dt > 0.0
            Bool combat = Player.IsInCombat()
            Bool free = (!combat || FSOC_InCombat.GetValue() == 1.0) && FSOC_PowerArmorAP.GetValue() == 1.0
            Float spent = 0.0
            If !free
                spent = Math.Max(LastAP - ap, 0.0)
            EndIf
            CorrectCore(dt, free, spent)
        EndIf
    EndIf
    LastAP = ap
    If coreWork
        StartTimer(CORE_INTERVAL)
    Else
        StartTimer(IDLE_INTERVAL)
    EndIf
EndEvent

; Actor::GetRestoreActorValueRate for ActionPoints divided by the sprint drain, negated: the perk multiplies
; the engine's per-frame drain by this, so the engine restores AP at the standing rate while sprinting.
Function UpdateRegenFactors()
    Float current = Player.GetValue(ActionPoints)
    Float percent = Player.GetValuePercentage(ActionPoints)
    If percent > 0.0
        MaxAP = current / percent
    EndIf
    Float factor = 0.0
    Float drain = VanillaSprintAP()
    If APRate && APRateMult && MaxAP > 0.0 && drain > 0.0
        Float regen = Player.GetValue(APRate) * 0.01 * MaxAP * Player.GetValue(APRateMult) * 0.01
        factor = 0.0 - regen / drain
    EndIf
    If Player.GetValue(FSOC_RegenFactor) != factor
        Player.SetValue(FSOC_RegenFactor, factor)
        Player.SetValue(FSOC_RegenFactorCombat, factor * CombatRegenMult)
    EndIf
EndFunction

; The engine drains the core for running time plus for every AP spent. Bring that to the chosen target.
Function CorrectCore(Float seconds, Bool free, Float spentAP)
    If !Battery || Player.GetValue(Battery) <= 0.0
        Return
    EndIf
    Float engine = RunDrainPerSecond * seconds + DrainPerAP * spentAP
    Float target
    If FSOC_PowerArmorCore.GetValue() == 1.0
        target = RunDrainPerSecond * SprintToRunRatio * seconds
    ElseIf free
        target = RunDrainPerSecond * seconds + DrainPerAP * VanillaSprintAP() * seconds
    Else
        Return
    EndIf
    Float delta = (target - engine) * Player.GetValue(PABatteryDamageRate)
    If delta > 0.0
        Player.DamageValue(Battery, delta)
    ElseIf delta < 0.0
        Player.RestoreValue(Battery, 0.0 - delta)
    EndIf
EndFunction

; AP per second a vanilla sprint costs (GamePlayFormulas::CalcSprintingActionPoints + vanilla perks).
Float Function VanillaSprintAP()
    Float value = SprintWeightBase * (SprintEndBase + SprintEndMult * Player.GetValue(Endurance)) * SprintDrainMult
    Int i = 0
    While i < SprintPerks.Length
        If Player.HasPerk(SprintPerks[i])
            If SprintPerkFunc[i] == FUNC_MULTIPLY
                value *= SprintPerkValue[i]
            ElseIf SprintPerkFunc[i] == FUNC_MULTIPLY_1_PLUS_AV
                value *= 1.0 + Player.GetValue(SprintPerkAV[i]) * SprintPerkValue[i]
            EndIf
        EndIf
        i += 1
    EndWhile
    Return Math.Max(value, 0.0)
EndFunction
