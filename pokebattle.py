"""
Grandmaster V9 Master Autonomous Agent for PokéDuel 3v3.
Final Production Architecture:
1. First-Strike Priority Law: Never gambles on slower Priority 0 moves when facing lethal damage;
   always banks guaranteed +2 Extreme Speed / +1 Bullet Punch damage before fainting.
2. Strict Setup Safety Floor & Flinch Veto: Forbids Swords Dance / Dragon Dance below 65% starting HP,
   below 38-45% post-hit HP, or into faster flinch moves (Rock Slide / Iron Head / Air Slash).
3. Temporal Discounting (gamma = 0.88^t) & Two-Tap Sash Breaker: Eliminates 4-turn Roost horizon
   illusions and rewards Turn-1 Hit + Turn-2 Priority KO sequences against Focus Sash / Multiscale.
4. Decoupled Forced-Switch Tracking & Mutual-KO Blind Switch Resilience: Never locks voluntary
   switching after a faint and protects 4x Fire-weak Scizor on double-blind entries.
100% Python Standard Library — Zero External Dependencies.
"""

import math


# ==============================================================================
# 1. CANONICAL TYPE CHART & MOVE / ROSTER DATABASES
# ==============================================================================

TYPE_CHART = {
    "Normal":   {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
    "Fire":     {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
    "Water":    {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
    "Grass":    {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
    "Ice":      {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
    "Poison":   {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0, "Fairy": 2.0},
    "Ground":   {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
    "Flying":   {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
    "Psychic":  {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0.0, "Steel": 0.5},
    "Bug":      {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
    "Rock":     {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
    "Ghost":    {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon":   {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
    "Steel":    {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
    "Dark":     {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
    "Fairy":    {"Fire": 0.5, "Fighting": 2.0, "Poison": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5},
}

SPECIAL_TYPES = {"Fire", "Water", "Electric", "Grass", "Ice", "Psychic", "Dragon", "Dark", "Fairy"}

# Baseline profiles for our locked-in 3-Pokemon core (auto-synced with runtime observations)
MY_TEAM_PROFILES = {
    "dragonite": {
        "types": ["Dragon", "Flying"],
        "base": {"hp": 91, "atk": 134, "def": 95, "spa": 100, "spd": 100, "spe": 80},
        "evs": {"hp": 4, "atk": 252, "def": 0, "spa": 0, "spd": 0, "spe": 252},
        "nature": {"atk": 1.1, "def": 1.0, "spa": 0.9, "spd": 1.0, "spe": 1.0},  # Adamant default
        "ability": "Multiscale",
        "item": "Lum Berry",
        "moves": ["extremespeed", "outrage", "dragondance", "firepunch"],
    },
    "scizor": {
        "types": ["Bug", "Steel"],
        "base": {"hp": 70, "atk": 130, "def": 100, "spa": 55, "spd": 80, "spe": 65},
        "evs": {"hp": 252, "atk": 252, "def": 4, "spa": 0, "spd": 0, "spe": 0},
        "nature": {"atk": 1.1, "def": 1.0, "spa": 0.9, "spd": 1.0, "spe": 1.0},  # Adamant Bulky Attacker
        "ability": "Technician",
        "item": "Life Orb",
        "moves": ["bulletpunch", "closecombat", "swordsdance", "xscissor"],
    },
    "lapras": {
        "types": ["Water", "Ice"],
        "base": {"hp": 130, "atk": 85, "def": 80, "spa": 85, "spd": 95, "spe": 60},
        "evs": {"hp": 252, "atk": 0, "def": 4, "spa": 252, "spd": 0, "spe": 0},
        "nature": {"atk": 0.9, "def": 1.0, "spa": 1.1, "spd": 1.0, "spe": 1.0},  # Modest Bulky Special
        "ability": "Water Absorb",
        "item": "Assault Vest",
        "moves": ["freezedry", "surf", "thunderbolt", "icebeam"],
    },
}

ROSTER_DB = {
    "garchomp": {
        "types": ["Dragon", "Ground"],
        "base": {"hp": 108, "atk": 130, "def": 95, "spa": 80, "spd": 85, "spe": 102},
        "abilities": ["Rough Skin", "Sand Veil"], "role": "physical_sweeper",
        "moves": ["earthquake", "outrage", "stoneedge", "swordsdance"],
    },
    "dragonite": {
        "types": ["Dragon", "Flying"],
        "base": {"hp": 91, "atk": 134, "def": 95, "spa": 100, "spd": 100, "spe": 80},
        "abilities": ["Multiscale", "Inner Focus"], "role": "physical_sweeper",
        "moves": ["extremespeed", "outrage", "dragonclaw", "earthquake", "firepunch", "dragondance"],
    },
    "tyranitar": {
        "types": ["Rock", "Dark"],
        "base": {"hp": 100, "atk": 134, "def": 110, "spa": 95, "spd": 100, "spe": 61},
        "abilities": ["Sand Stream", "Unnerve"], "role": "physical_tank",
        "moves": ["stoneedge", "crunch", "earthquake", "icepunch"],
    },
    "metagross": {
        "types": ["Steel", "Psychic"],
        "base": {"hp": 80, "atk": 135, "def": 130, "spa": 95, "spd": 90, "spe": 70},
        "abilities": ["Clear Body", "Light Metal"], "role": "physical_tank",
        "moves": ["meteormash", "bulletpunch", "earthquake", "zenheadbutt"],
    },
    "salamence": {
        "types": ["Dragon", "Flying"],
        "base": {"hp": 95, "atk": 135, "def": 80, "spa": 110, "spd": 80, "spe": 100},
        "abilities": ["Intimidate", "Moxie"], "role": "mixed_sweeper",
        "moves": ["dracometeor", "flamethrower", "earthquake", "roost", "outrage", "dragondance"],
    },
    "hydreigon": {
        "types": ["Dark", "Dragon"],
        "base": {"hp": 92, "atk": 105, "def": 90, "spa": 125, "spd": 90, "spe": 98},
        "abilities": ["Levitate"], "role": "special_sweeper",
        "moves": ["darkpulse", "dracometeor", "flamethrower", "flashcannon"],
    },
    "dragapult": {
        "types": ["Dragon", "Ghost"],
        "base": {"hp": 88, "atk": 120, "def": 75, "spa": 100, "spd": 75, "spe": 142},
        "abilities": ["Infiltrator", "Clear Body"], "role": "mixed_sweeper",
        "moves": ["dragondarts", "dracometeor", "shadowball", "flamethrower", "thunderbolt", "phantomforce", "uturn"],
    },
    "volcarona": {
        "types": ["Bug", "Fire"],
        "base": {"hp": 85, "atk": 60, "def": 65, "spa": 135, "spd": 105, "spe": 100},
        "abilities": ["Flame Body", "Swarm"], "role": "special_sweeper",
        "moves": ["fierydance", "bugbuzz", "gigadrain", "quiverdance"],
    },
    "lucario": {
        "types": ["Fighting", "Steel"],
        "base": {"hp": 70, "atk": 110, "def": 70, "spa": 115, "spd": 70, "spe": 90},
        "abilities": ["Inner Focus", "Steadfast", "Justified"], "role": "physical_sweeper",
        "moves": ["closecombat", "meteormash", "extremespeed", "flashcannon", "swordsdance"],
    },
    "scizor": {
        "types": ["Bug", "Steel"],
        "base": {"hp": 70, "atk": 130, "def": 100, "spa": 55, "spd": 80, "spe": 65},
        "abilities": ["Technician", "Swarm"], "role": "physical_tank",
        "moves": ["bulletpunch", "closecombat", "swordsdance", "uturn", "xscissor"],
    },
    "gengar": {
        "types": ["Ghost", "Poison"],
        "base": {"hp": 60, "atk": 65, "def": 60, "spa": 130, "spd": 75, "spe": 110},
        "abilities": ["Cursed Body"], "role": "special_sweeper",
        "moves": ["shadowball", "sludgebomb", "focusblast", "thunderbolt"],
    },
    "gyarados": {
        "types": ["Water", "Flying"],
        "base": {"hp": 95, "atk": 125, "def": 79, "spa": 60, "spd": 100, "spe": 81},
        "abilities": ["Intimidate", "Moxie"], "role": "physical_sweeper",
        "moves": ["waterfall", "earthquake", "icefang", "dragondance"],
    },
    "charizard": {
        "types": ["Fire", "Flying"],
        "base": {"hp": 78, "atk": 84, "def": 78, "spa": 109, "spd": 85, "spe": 100},
        "abilities": ["Blaze", "Solar Power"], "role": "special_sweeper",
        "moves": ["flamethrower", "airslash", "focusblast", "dragonpulse"],
    },
    "blastoise": {
        "types": ["Water"],
        "base": {"hp": 79, "atk": 83, "def": 100, "spa": 85, "spd": 105, "spe": 78},
        "abilities": ["Torrent", "Rain Dish"], "role": "special_tank",
        "moves": ["hydropump", "icebeam", "flashcannon", "protect", "surf"],
    },
    "venusaur": {
        "types": ["Grass", "Poison"],
        "base": {"hp": 80, "atk": 82, "def": 83, "spa": 100, "spd": 100, "spe": 80},
        "abilities": ["Overgrow", "Chlorophyll"], "role": "special_tank",
        "moves": ["gigadrain", "sludgebomb", "earthpower", "sleeppowder"],
    },
    "arcanine": {
        "types": ["Fire"],
        "base": {"hp": 90, "atk": 110, "def": 80, "spa": 100, "spd": 80, "spe": 95},
        "abilities": ["Intimidate", "Flash Fire", "Justified"], "role": "physical_sweeper",
        "moves": ["flareblitz", "extremespeed", "wildcharge", "willowisp"],
    },
    "excadrill": {
        "types": ["Ground", "Steel"],
        "base": {"hp": 110, "atk": 135, "def": 60, "spa": 50, "spd": 65, "spe": 88},
        "abilities": ["Mold Breaker", "Sand Rush", "Sand Force"], "role": "physical_sweeper",
        "moves": ["earthquake", "ironhead", "rockslide", "swordsdance"],
    },
    "togekiss": {
        "types": ["Fairy", "Flying"],
        "base": {"hp": 85, "atk": 50, "def": 95, "spa": 120, "spd": 115, "spe": 80},
        "abilities": ["Serene Grace", "Super Luck"], "role": "special_tank",
        "moves": ["airslash", "dazzlinggleam", "aurasphere", "roost"],
    },
    "snorlax": {
        "types": ["Normal"],
        "base": {"hp": 160, "atk": 110, "def": 65, "spa": 65, "spd": 110, "spe": 30},
        "abilities": ["Thick Fat", "Immunity"], "role": "physical_tank",
        "moves": ["bodyslam", "earthquake", "crunch", "rest"],
    },
    "alakazam": {
        "types": ["Psychic"],
        "base": {"hp": 55, "atk": 50, "def": 45, "spa": 135, "spd": 95, "spe": 120},
        "abilities": ["Magic Guard", "Synchronize", "Inner Focus"], "role": "special_sweeper",
        "moves": ["psychic", "shadowball", "focusblast", "energyball"],
    },
    "lapras": {
        "types": ["Water", "Ice"],
        "base": {"hp": 130, "atk": 85, "def": 80, "spa": 85, "spd": 95, "spe": 60},
        "abilities": ["Water Absorb", "Shell Armor"], "role": "special_tank",
        "moves": ["freezedry", "hydropump", "surf", "thunderbolt", "icebeam"],
    },
    "corviknight": {
        "types": ["Flying", "Steel"],
        "base": {"hp": 98, "atk": 87, "def": 105, "spa": 53, "spd": 85, "spe": 67},
        "abilities": ["Mirror Armor", "Pressure"], "role": "physical_tank",
        "moves": ["bravebird", "bodypress", "roost", "irondefense"],
    },
    "ferrothorn": {
        "types": ["Grass", "Steel"],
        "base": {"hp": 74, "atk": 94, "def": 131, "spa": 54, "spd": 116, "spe": 20},
        "abilities": ["Iron Barbs"], "role": "physical_tank",
        "moves": ["powerwhip", "gyroball", "leechseed", "protect"],
    },
    "greninja": {
        "types": ["Water", "Dark"],
        "base": {"hp": 72, "atk": 95, "def": 67, "spa": 103, "spd": 71, "spe": 122},
        "abilities": ["Protean", "Torrent"], "role": "special_sweeper",
        "moves": ["hydropump", "darkpulse", "icebeam", "uturn", "surf"],
    },
}

MOVE_DB = {
    "earthquake":   {"type": "Ground", "cat": "Physical", "bp": 100, "acc": 100, "prio": 0, "contact": False},
    "outrage":      {"type": "Dragon", "cat": "Physical", "bp": 120, "acc": 100, "prio": 0, "lock": True, "contact": True},
    "dragonclaw":   {"type": "Dragon", "cat": "Physical", "bp": 80, "acc": 100, "prio": 0, "contact": True},
    "stoneedge":    {"type": "Rock", "cat": "Physical", "bp": 100, "acc": 80, "prio": 0, "contact": False},
    "swordsdance":  {"type": "Normal", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "boosts": {"atk": 2}},
    "extremespeed": {"type": "Normal", "cat": "Physical", "bp": 80, "acc": 100, "prio": 2, "contact": True},
    "firepunch":    {"type": "Fire", "cat": "Physical", "bp": 75, "acc": 100, "prio": 0, "contact": True},
    "thunderpunch": {"type": "Electric", "cat": "Physical", "bp": 75, "acc": 100, "prio": 0, "contact": True},
    "dragondance":  {"type": "Dragon", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "boosts": {"atk": 1, "spe": 1}},
    "crunch":       {"type": "Dark", "cat": "Physical", "bp": 80, "acc": 100, "prio": 0, "contact": True},
    "icepunch":     {"type": "Ice", "cat": "Physical", "bp": 75, "acc": 100, "prio": 0, "contact": True},
    "meteormash":   {"type": "Steel", "cat": "Physical", "bp": 90, "acc": 90, "prio": 0, "contact": True, "sec_boost": 0.2},
    "bulletpunch":  {"type": "Steel", "cat": "Physical", "bp": 40, "acc": 100, "prio": 1, "contact": True},
    "zenheadbutt":  {"type": "Psychic", "cat": "Physical", "bp": 80, "acc": 90, "prio": 0, "contact": True, "flinch": 0.20},
    "dracometeor":  {"type": "Dragon", "cat": "Special", "bp": 130, "acc": 90, "prio": 0, "self_drop": {"spa": -2}},
    "flamethrower": {"type": "Fire", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "fireblast":    {"type": "Fire", "cat": "Special", "bp": 110, "acc": 85, "prio": 0},
    "roost":        {"type": "Flying", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "heal": 50.0, "roost": True},
    "darkpulse":    {"type": "Dark", "cat": "Special", "bp": 80, "acc": 100, "prio": 0, "flinch": 0.20},
    "flashcannon":  {"type": "Steel", "cat": "Special", "bp": 80, "acc": 100, "prio": 0},
    "dragondarts":  {"type": "Dragon", "cat": "Physical", "bp": 50, "acc": 100, "prio": 0, "hits": 2, "contact": False},
    "phantomforce": {"type": "Ghost", "cat": "Physical", "bp": 90, "acc": 100, "prio": 0, "two_turn": True, "contact": True},
    "uturn":        {"type": "Bug", "cat": "Physical", "bp": 70, "acc": 100, "prio": 0, "pivot": True, "contact": True},
    "xscissor":     {"type": "Bug", "cat": "Physical", "bp": 80, "acc": 100, "prio": 0, "contact": True},
    "fierydance":   {"type": "Fire", "cat": "Special", "bp": 80, "acc": 100, "prio": 0, "sec_boost": 0.5},
    "bugbuzz":      {"type": "Bug", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "gigadrain":    {"type": "Grass", "cat": "Special", "bp": 75, "acc": 100, "prio": 0, "drain": 0.5},
    "quiverdance":  {"type": "Bug", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "boosts": {"spa": 1, "spd": 1, "spe": 1}},
    "closecombat":  {"type": "Fighting", "cat": "Physical", "bp": 120, "acc": 100, "prio": 0, "self_drop": {"def": -1, "spd": -1}, "contact": True},
    "shadowball":   {"type": "Ghost", "cat": "Special", "bp": 80, "acc": 100, "prio": 0},
    "sludgebomb":   {"type": "Poison", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "focusblast":   {"type": "Fighting", "cat": "Special", "bp": 120, "acc": 70, "prio": 0},
    "thunderbolt":  {"type": "Electric", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "thunder":      {"type": "Electric", "cat": "Special", "bp": 110, "acc": 70, "prio": 0},
    "waterfall":    {"type": "Water", "cat": "Physical", "bp": 80, "acc": 100, "prio": 0, "contact": True, "flinch": 0.20},
    "aquatail":     {"type": "Water", "cat": "Physical", "bp": 90, "acc": 90, "prio": 0, "contact": True},
    "icefang":      {"type": "Ice", "cat": "Physical", "bp": 65, "acc": 95, "prio": 0, "contact": True, "flinch": 0.10},
    "airslash":     {"type": "Flying", "cat": "Special", "bp": 75, "acc": 95, "prio": 0, "flinch": 0.30},
    "hurricane":    {"type": "Flying", "cat": "Special", "bp": 110, "acc": 70, "prio": 0},
    "dragonpulse":  {"type": "Dragon", "cat": "Special", "bp": 85, "acc": 100, "prio": 0},
    "hydropump":    {"type": "Water", "cat": "Special", "bp": 110, "acc": 80, "prio": 0},
    "surf":         {"type": "Water", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "scald":        {"type": "Water", "cat": "Special", "bp": 80, "acc": 100, "prio": 0},
    "icebeam":      {"type": "Ice", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "blizzard":     {"type": "Ice", "cat": "Special", "bp": 110, "acc": 70, "prio": 0},
    "protect":      {"type": "Normal", "cat": "Status", "bp": 0, "acc": 100, "prio": 4, "protect": True},
    "earthpower":   {"type": "Ground", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "sleeppowder":  {"type": "Grass", "cat": "Status", "bp": 0, "acc": 75, "prio": 0, "status": "slp"},
    "flareblitz":   {"type": "Fire", "cat": "Physical", "bp": 120, "acc": 100, "prio": 0, "recoil": 0.33, "contact": True},
    "wildcharge":   {"type": "Electric", "cat": "Physical", "bp": 90, "acc": 100, "prio": 0, "recoil": 0.25, "contact": True},
    "willowisp":    {"type": "Fire", "cat": "Status", "bp": 0, "acc": 85, "prio": 0, "status": "brn"},
    "ironhead":     {"type": "Steel", "cat": "Physical", "bp": 80, "acc": 100, "prio": 0, "contact": True, "flinch": 0.30},
    "rockslide":    {"type": "Rock", "cat": "Physical", "bp": 75, "acc": 90, "prio": 0, "contact": False, "flinch": 0.30},
    "brickbreak":   {"type": "Fighting", "cat": "Physical", "bp": 75, "acc": 100, "prio": 0, "contact": True},
    "superpower":   {"type": "Fighting", "cat": "Physical", "bp": 120, "acc": 100, "prio": 0, "self_drop": {"atk": -1, "def": -1}, "contact": True},
    "dazzlinggleam":{"type": "Fairy", "cat": "Special", "bp": 80, "acc": 100, "prio": 0},
    "moonblast":    {"type": "Fairy", "cat": "Special", "bp": 95, "acc": 100, "prio": 0},
    "playrough":    {"type": "Fairy", "cat": "Physical", "bp": 90, "acc": 90, "prio": 0, "contact": True},
    "aurasphere":   {"type": "Fighting", "cat": "Special", "bp": 80, "acc": 100, "prio": 0},
    "bodyslam":     {"type": "Normal", "cat": "Physical", "bp": 85, "acc": 100, "prio": 0, "contact": True},
    "doubleedge":   {"type": "Normal", "cat": "Physical", "bp": 120, "acc": 100, "prio": 0, "recoil": 0.33, "contact": True},
    "rest":         {"type": "Psychic", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "heal": 100.0},
    "psychic":      {"type": "Psychic", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "psyshock":     {"type": "Psychic", "cat": "Special", "bp": 80, "acc": 100, "prio": 0},
    "energyball":   {"type": "Grass", "cat": "Special", "bp": 90, "acc": 100, "prio": 0},
    "freezedry":    {"type": "Ice", "cat": "Special", "bp": 70, "acc": 100, "prio": 0, "freeze_dry": True},
    "bravebird":    {"type": "Flying", "cat": "Physical", "bp": 120, "acc": 100, "prio": 0, "recoil": 0.33, "contact": True},
    "dualwingbeat": {"type": "Flying", "cat": "Physical", "bp": 40, "acc": 90, "prio": 0, "hits": 2, "contact": True},
    "bodypress":    {"type": "Fighting", "cat": "Physical", "bp": 80, "acc": 100, "prio": 0, "use_def": True, "contact": True},
    "irondefense":  {"type": "Steel", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "boosts": {"def": 2}},
    "powerwhip":    {"type": "Grass", "cat": "Physical", "bp": 120, "acc": 85, "prio": 0, "contact": True},
    "gyroball":     {"type": "Steel", "cat": "Physical", "bp": 85, "acc": 100, "prio": 0, "contact": True},
    "leechseed":    {"type": "Grass", "cat": "Status", "bp": 0, "acc": 90, "prio": 0, "leech": True},
    "aquajet":      {"type": "Water", "cat": "Physical", "bp": 40, "acc": 100, "prio": 1, "contact": True},
    "iceshard":     {"type": "Ice", "cat": "Physical", "bp": 40, "acc": 100, "prio": 1, "contact": False},
    "machpunch":    {"type": "Fighting", "cat": "Physical", "bp": 40, "acc": 100, "prio": 1, "contact": True},
    "shadowsneak":  {"type": "Ghost", "cat": "Physical", "bp": 40, "acc": 100, "prio": 1, "contact": True},
    "suckerpunch":  {"type": "Dark", "cat": "Physical", "bp": 70, "acc": 100, "prio": 1, "contact": True},
    "quickattack":  {"type": "Normal", "cat": "Physical", "bp": 40, "acc": 100, "prio": 1, "contact": True},
    "calmmind":     {"type": "Psychic", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "boosts": {"spa": 1, "spd": 1}},
    "nastyplot":    {"type": "Dark", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "boosts": {"spa": 2}},
    "bulkup":       {"type": "Fighting", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "boosts": {"atk": 1, "def": 1}},
    "recover":      {"type": "Normal", "cat": "Status", "bp": 0, "acc": 100, "prio": 0, "heal": 50.0},
    "thunderwave":  {"type": "Electric", "cat": "Status", "bp": 0, "acc": 90, "prio": 0, "status": "par"},
    "toxic":        {"type": "Poison", "cat": "Status", "bp": 0, "acc": 90, "prio": 0, "status": "tox"},
    "voltswitch":   {"type": "Electric", "cat": "Special", "bp": 70, "acc": 100, "prio": 0, "pivot": True},
    "knockoff":     {"type": "Dark", "cat": "Physical", "bp": 65, "acc": 100, "prio": 0, "contact": True},
}


def norm_id(text: str) -> str:
    if not text:
        return ""
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def resolve_species(raw_name: str) -> str:
    nid = norm_id(raw_name)
    if nid in ROSTER_DB:
        return nid
    for k in ROSTER_DB:
        if k in nid:
            return k
    return nid


def resolve_move(move_dict: dict) -> str:
    mid = norm_id(move_dict.get("id") or move_dict.get("name", ""))
    if mid in MOVE_DB:
        return mid
    for k in MOVE_DB:
        if k == mid or (len(k) >= 6 and k in mid):
            return k
    return mid


def normalize_types(type_list: list, fallback_species_id: str = "") -> list:
    canonical = ROSTER_DB.get(fallback_species_id, {}).get("types", [])
    if canonical:
        return list(canonical)
    if not type_list:
        return ["Normal"]
    cleaned = [str(t).strip().capitalize() for t in type_list if t]
    return cleaned if cleaned else ["Normal"]


def primary_ability(species_id: str, is_ours: bool = False) -> str:
    if is_ours and species_id in MY_TEAM_PROFILES:
        return MY_TEAM_PROFILES[species_id]["ability"]
    abilities = ROSTER_DB.get(species_id, {}).get("abilities", [])
    return abilities[0] if abilities else ""


def has_ability(species_id: str, ability_name: str) -> bool:
    return ability_name in ROSTER_DB.get(species_id, {}).get("abilities", [])


def stage_mult(stage: int) -> float:
    stage = max(-6, min(6, int(stage or 0)))
    return (2.0 + stage) / 2.0 if stage >= 0 else 2.0 / (2.0 - stage)


def get_type_effectiveness(move_type: str, def_types: list, is_freeze_dry: bool = False) -> float:
    if not move_type or not def_types:
        return 1.0
    mt = str(move_type).strip().capitalize()
    mult = 1.0
    for dt_raw in def_types:
        dt = str(dt_raw).strip().capitalize()
        if is_freeze_dry and dt == "Water":
            mult *= 2.0
        else:
            mult *= TYPE_CHART.get(mt, {}).get(dt, 1.0)
    return mult


def parse_condition(cond_str: str, fallback_hp_pct: float = 100.0) -> dict:
    res = {"hp_pct": float(fallback_hp_pct), "cur_hp": None, "max_hp": None, "status": ""}
    if not cond_str:
        return res
    parts = str(cond_str).strip().split()
    if parts:
        hp_part = parts[0]
        if "/" in hp_part:
            try:
                cur_s, max_s = hp_part.split("/", 1)
                cur_v = float(cur_s)
                max_v = float(max_s)
                if max_v > 0:
                    res["cur_hp"] = cur_v
                    res["max_hp"] = max_v
                    res["hp_pct"] = (cur_v / max_v) * 100.0
            except Exception:
                pass
        if len(parts) > 1:
            res["status"] = parts[1].lower()
    return res


# ==============================================================================
# 2. SELF-AWARE FIRST-PRINCIPLES ROLLOUT AGENT (V9 MASTER)
# ==============================================================================

class PokemonAgent:
    """
    PokéDuel 3v3 Grandmaster V9 Master Agent.
    Combines exact self-team modeling (Dragonite + Scizor + Lapras) with temporally
    discounted (gamma = 0.88^t) 4-turn rollout math, strict first-strike priority
    execution when in lethal range, and a 65% HP / 38-45% post-hit setup safety floor.
    """

    def __init__(self):
        self._reset_battle_memory()

    def _reset_battle_memory(self):
        self.last_turn = -1
        self.seen_foes = {}
        self.my_known_moves = {
            k: [{"id": m, "name": m} for m in v["moves"]]
            for k, v in MY_TEAM_PROFILES.items()
        }
        self.my_max_hp_cache = {}
        self.my_raw_stats_cache = {}
        self.my_lum_intact = True
        self.last_foe_id = None
        self.last_my_id = None
        self.last_my_hp = 100.0
        self.last_foe_hp = 100.0
        self.last_action_type = None
        self.last_voluntary_switch_foe = None
        self.last_move_id = None
        self.last_expected_dmg = 0.0
        self.last_move_cat = None
        self.we_outsped_expected = False
        self.opponent_mode = "GREEDY"
        self.my_tracked_boosts = {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
        self.sand_turns = 0

    # --------------------------------------------------------------------------
    # EXACT SELF-TEAM & FOE STAT ENGINE
    # --------------------------------------------------------------------------

    def _get_effective_my_boosts(self, obs_boosts: dict) -> dict:
        obs_b = obs_boosts or {}
        merged = {}
        for stat in ("atk", "def", "spa", "spd", "spe"):
            ob_val = int(obs_b.get(stat, 0) or 0)
            tr_val = int(self.my_tracked_boosts.get(stat, 0) or 0)
            merged[stat] = ob_val if ob_val != 0 else tr_val
        return merged

    def _estimate_stats(
        self,
        poke_name: str,
        boosts: dict = None,
        status: str = "",
        is_ours: bool = False,
        raw_stats: dict = None,
        parsed_max_hp: float = None,
    ) -> dict:
        pid = resolve_species(poke_name)

        if is_ours and parsed_max_hp:
            self.my_max_hp_cache[pid] = parsed_max_hp
        elif is_ours and pid in self.my_max_hp_cache:
            parsed_max_hp = self.my_max_hp_cache[pid]

        if is_ours and isinstance(raw_stats, dict) and raw_stats:
            self.my_raw_stats_cache[pid] = dict(raw_stats)
        elif is_ours and pid in self.my_raw_stats_cache and not raw_stats:
            raw_stats = self.my_raw_stats_cache[pid]

        if is_ours and pid in MY_TEAM_PROFILES:
            prof = MY_TEAM_PROFILES[pid]
            base = prof["base"]
            evs = prof["evs"]
            nat = prof["nature"]
            ptypes = prof["types"]

            hp = int(parsed_max_hp) if parsed_max_hp else int((2 * base["hp"] + 31 + (evs["hp"] // 4)) + 110)
            atk = int(((2 * base["atk"] + 31 + (evs["atk"] // 4)) + 5) * nat["atk"])
            dfn = int(((2 * base["def"] + 31 + (evs["def"] // 4)) + 5) * nat["def"])
            spa = int(((2 * base["spa"] + 31 + (evs["spa"] // 4)) + 5) * nat["spa"])
            spd = int(((2 * base["spd"] + 31 + (evs["spd"] // 4)) + 5) * nat["spd"])
            spe = int(((2 * base["spe"] + 31 + (evs["spe"] // 4)) + 5) * nat["spe"])

            if isinstance(raw_stats, dict):
                hp = int(raw_stats.get("hp", hp) or hp)
                atk = int(raw_stats.get("atk", atk) or atk)
                dfn = int(raw_stats.get("def", dfn) or dfn)
                spa = int(raw_stats.get("spa", spa) or spa)
                spd = int(raw_stats.get("spd", spd) or spd)
                spe = int(raw_stats.get("spe", spe) or spe)

            boosts = boosts or {}
            atk = int(atk * stage_mult(boosts.get("atk", 0)))
            dfn = int(dfn * stage_mult(boosts.get("def", 0)))
            spa = int(spa * stage_mult(boosts.get("spa", 0)))
            spd = int(spd * stage_mult(boosts.get("spd", 0)))
            spe = int(spe * stage_mult(boosts.get("spe", 0)))

            if "par" in str(status or "").lower():
                spe = int(spe * 0.5)

            if prof.get("item") == "Assault Vest":
                spd = int(spd * 1.5)

            if self.sand_turns > 0 and "Rock" in ptypes:
                spd = int(spd * 1.5)

            return {"hp": hp, "atk": atk, "def": dfn, "spa": spa, "spd": spd, "spe": spe}

        entry = ROSTER_DB.get(pid, {
            "types": ["Normal"],
            "base": {"hp": 85, "atk": 100, "def": 85, "spa": 100, "spd": 85, "spe": 90},
            "abilities": [""],
            "role": "physical_sweeper",
        })
        base = entry["base"]
        role = entry.get("role", "physical_sweeper")
        ptypes = entry.get("types", ["Normal"])

        hp_ev, atk_ev, def_ev, spa_ev, spd_ev, spe_ev = 4, 0, 0, 0, 0, 0
        atk_nat, def_nat, spa_nat, spd_nat, spe_nat = 1.0, 1.0, 1.0, 1.0, 1.0

        if role == "physical_sweeper":
            atk_ev, spe_ev = 252, 252
            spe_nat = 1.1 if base["spe"] >= 88 else 1.0
            atk_nat = 1.1 if spe_nat == 1.0 else 1.0
        elif role == "special_sweeper":
            spa_ev, spe_ev = 252, 252
            spe_nat = 1.1 if base["spe"] >= 88 else 1.0
            spa_nat = 1.1 if spe_nat == 1.0 else 1.0
        elif role == "mixed_sweeper":
            atk_ev, spa_ev, spe_ev = 168, 168, 252
            spe_nat = 1.1
        elif role == "physical_tank":
            hp_ev, atk_ev = 252, 252
            atk_nat = 1.1
        elif role == "special_tank":
            hp_ev, spa_ev = 252, 252
            spa_nat = 1.1

        hp = int(parsed_max_hp) if parsed_max_hp else int((2 * base["hp"] + 31 + (hp_ev // 4)) + 110)
        atk = int(((2 * base["atk"] + 31 + (atk_ev // 4)) + 5) * atk_nat)
        dfn = int(((2 * base["def"] + 31 + (def_ev // 4)) + 5) * def_nat)
        spa = int(((2 * base["spa"] + 31 + (spa_ev // 4)) + 5) * spa_nat)
        spd = int(((2 * base["spd"] + 31 + (spd_ev // 4)) + 5) * spd_nat)
        spe = int(((2 * base["spe"] + 31 + (spe_ev // 4)) + 5) * spe_nat)

        boosts = boosts or {}
        atk = int(atk * stage_mult(boosts.get("atk", 0)))
        dfn = int(dfn * stage_mult(boosts.get("def", 0)))
        spa = int(spa * stage_mult(boosts.get("spa", 0)))
        spd = int(spd * stage_mult(boosts.get("spd", 0)))
        spe = int(spe * stage_mult(boosts.get("spe", 0)))

        if "par" in str(status or "").lower():
            spe = int(spe * 0.5)

        if self.sand_turns > 0 or primary_ability(pid, is_ours=False) == "Sand Stream":
            if "Rock" in ptypes:
                spd = int(spd * 1.5)
            if not is_ours and has_ability(pid, "Sand Rush"):
                spe = int(spe * 2.0)

        if not is_ours and pid in self.seen_foes:
            fmem = self.seen_foes[pid]
            if fmem.get("choice_scarf"):
                spe = int(spe * 1.5)
            spd = int(spd * fmem.get("spdef_mult", 1.0))
            dfn = int(dfn * fmem.get("def_mult", 1.0))

        return {"hp": hp, "atk": atk, "def": dfn, "spa": spa, "spd": spd, "spe": spe}

    def _estimate_damage_rolls(
        self,
        atk_name: str,
        atk_types: list,
        atk_stats: dict,
        atk_status: str,
        def_name: str,
        def_types: list,
        def_stats: dict,
        def_hp_pct: float,
        move_info: dict,
        is_our_attack: bool = True,
    ) -> dict:
        zero_res = {
            "min": 0.0, "avg": 0.0, "max": 0.0, "type_mult": 0.0,
            "contact": False, "recoil_pct": 0.0, "drain_pct": 0.0, "flinch_prob": 0.0,
        }
        mid = resolve_move(move_info)
        m_meta = MOVE_DB.get(mid, {})

        atk_id = resolve_species(atk_name)
        def_id = resolve_species(def_name)

        canon_atk_types = normalize_types(atk_types, atk_id)
        canon_def_types = list(def_types) if def_types else normalize_types(def_types, def_id)

        raw_type = move_info.get("type") or m_meta.get("type") or "Normal"
        move_type = str(raw_type).strip().capitalize()

        raw_cat = move_info.get("category") or m_meta.get("cat")
        if raw_cat:
            cat = str(raw_cat).strip().capitalize()
        else:
            if (move_info.get("base_power") or m_meta.get("bp") or 0) == 0:
                cat = "Status"
            else:
                cat = "Special" if move_type in SPECIAL_TYPES else "Physical"

        if cat == "Status" or (move_info.get("base_power") == 0 and m_meta.get("bp", 0) == 0):
            return zero_res

        bp = float(move_info.get("base_power") or m_meta.get("bp") or 0)
        if bp <= 0:
            return zero_res

        atk_ability = primary_ability(atk_id, is_ours=is_our_attack)
        def_ability = primary_ability(def_id, is_ours=(not is_our_attack))
        mold_breaker = (atk_ability == "Mold Breaker")
        is_freeze_dry = (mid == "freezedry") or m_meta.get("freeze_dry", False)

        if not mold_breaker:
            if def_ability == "Water Absorb" and move_type == "Water":
                return zero_res
            if def_ability == "Levitate" and move_type == "Ground":
                return zero_res
            if def_ability == "Flash Fire" and move_type == "Fire":
                return zero_res

        type_mult = get_type_effectiveness(move_type, canon_def_types, is_freeze_dry=is_freeze_dry)
        if type_mult <= 0.0:
            return zero_res

        hits = m_meta.get("hits", 1)
        if atk_ability == "Technician" and bp <= 60:
            bp *= 1.5

        if mid == "gyroball":
            atk_spe = max(1, atk_stats.get("spe", 50))
            def_spe = max(1, def_stats.get("spe", 200))
            bp = min(150.0, 25.0 * (def_spe / atk_spe) + 1.0)

        if mid == "bodypress" or m_meta.get("use_def"):
            a_stat = float(atk_stats.get("def", 200))
            d_stat = float(def_stats.get("def", 200))
        elif cat == "Physical":
            a_stat = float(atk_stats.get("atk", 250))
            d_stat = float(def_stats.get("def", 200))
            if "brn" in str(atk_status or "").lower():
                a_stat *= 0.5
        else:
            a_stat = float(atk_stats.get("spa", 250))
            d_stat = float(def_stats.get("spd", 200))

        if move_info.get("stab") is True or move_type in canon_atk_types or atk_ability == "Protean":
            stab = 1.5
        else:
            stab = 1.0

        ability_def_mod = 1.0
        if not mold_breaker and def_ability == "Thick Fat" and move_type in ("Fire", "Ice"):
            ability_def_mod *= 0.5

        if is_our_attack:
            my_item = MY_TEAM_PROFILES.get(atk_id, {}).get("item", "")
            item_mod = 1.3 if my_item == "Life Orb" else 1.0
        else:
            atk_role = ROSTER_DB.get(atk_id, {}).get("role", "physical_sweeper")
            item_mod = 1.15 if "sweeper" in atk_role else 1.05

        base_hit_dmg = (((42.0 * bp * (a_stat / max(1.0, d_stat))) / 50.0) + 2.0)
        unrolled_single = base_hit_dmg * stab * type_mult * ability_def_mod * item_mod

        multiscale_active = (not mold_breaker and def_ability == "Multiscale" and def_hp_pct >= 99.0)
        total_unrolled = 0.0
        for h in range(hits):
            if h == 0 and multiscale_active:
                total_unrolled += unrolled_single * 0.5
            else:
                total_unrolled += unrolled_single

        def_max_hp = float(max(1, def_stats.get("hp", 300)))
        max_pct = (total_unrolled * 1.00 / def_max_hp) * 100.0
        avg_pct = (total_unrolled * 0.925 / def_max_hp) * 100.0
        min_pct = (total_unrolled * 0.85 / def_max_hp) * 100.0

        is_contact = m_meta.get("contact", cat == "Physical" and mid not in ("earthquake", "stoneedge", "rockslide", "dragondarts"))
        self_recoil_pct = 0.0
        if is_contact and def_ability in ("Rough Skin", "Iron Barbs"):
            self_recoil_pct += 12.5
        if is_our_attack and MY_TEAM_PROFILES.get(atk_id, {}).get("item") == "Life Orb":
            self_recoil_pct += 10.0
        if m_meta.get("recoil"):
            self_recoil_pct += min(avg_pct, def_hp_pct) * float(m_meta["recoil"]) * (def_max_hp / max(1.0, float(atk_stats.get("hp", 300))))

        drain_pct = 0.0
        if m_meta.get("drain"):
            drain_pct = min(avg_pct, def_hp_pct) * float(m_meta["drain"]) * (def_max_hp / max(1.0, float(atk_stats.get("hp", 300))))

        flinch_prob = float(m_meta.get("flinch", 0.0))
        if flinch_prob > 0.0:
            if def_ability == "Inner Focus":
                flinch_prob = 0.0
            elif atk_ability == "Serene Grace":
                flinch_prob = min(1.0, flinch_prob * 2.0)

        return {
            "min": min_pct,
            "avg": avg_pct,
            "max": max_pct,
            "type_mult": type_mult,
            "contact": is_contact,
            "recoil_pct": self_recoil_pct,
            "drain_pct": drain_pct,
            "flinch_prob": flinch_prob,
        }

    def _estimate_foe_threat(
        self,
        foe_name: str,
        foe_types: list,
        foe_stats: dict,
        foe_status: str,
        target_name: str,
        target_types: list,
        target_stats: dict,
        target_hp_pct: float,
    ) -> dict:
        fid = resolve_species(foe_name)
        f_entry = ROSTER_DB.get(fid, {})
        candidate_moves = list(f_entry.get("moves", []))

        max_dmg = 0.0
        avg_dmg = 0.0
        best_move = ""
        best_move_type = "Normal"
        prio_max_dmg = 0.0
        best_flinch_prob = 0.0
        flinch_move_dmg = 0.0
        heal_amount = 0.0
        has_roost = False
        inflicts_status = ""

        if not candidate_moves:
            for ft in normalize_types(foe_types, fid):
                fake_move = {"id": "generic", "type": ft, "category": "Physical", "base_power": 90}
                rolls = self._estimate_damage_rolls(
                    foe_name, foe_types, foe_stats, foe_status,
                    target_name, target_types, target_stats, target_hp_pct,
                    fake_move, is_our_attack=False,
                )
                if rolls["max"] > max_dmg:
                    max_dmg = rolls["max"]
                    avg_dmg = rolls["avg"]
                    best_move = "generic"
                    best_move_type = ft
            return {
                "max_dmg": max_dmg, "avg_dmg": avg_dmg, "best_move": best_move, "best_move_type": best_move_type,
                "prio_dmg": 0.0, "flinch_prob": 0.0, "flinch_dmg": 0.0, "heal_amount": 0.0,
                "has_roost": False, "inflicts_status": "",
            }

        for mid in candidate_moves:
            m_meta = MOVE_DB.get(mid, {})
            if not m_meta:
                continue
            if m_meta.get("cat") == "Status":
                if m_meta.get("heal", 0.0) > heal_amount:
                    heal_amount = float(m_meta["heal"])
                if m_meta.get("roost"):
                    has_roost = True
                if m_meta.get("status"):
                    inflicts_status = m_meta["status"]
                continue

            rolls = self._estimate_damage_rolls(
                foe_name, foe_types, foe_stats, foe_status,
                target_name, target_types, target_stats, target_hp_pct,
                {"id": mid, "name": mid, "type": m_meta["type"], "category": m_meta["cat"], "base_power": m_meta["bp"]},
                is_our_attack=False,
            )
            if rolls["max"] > max_dmg:
                max_dmg = rolls["max"]
                avg_dmg = rolls["avg"]
                best_move = mid
                best_move_type = m_meta.get("type", "Normal")
            if m_meta.get("prio", 0) > 0 and rolls["max"] > prio_max_dmg:
                prio_max_dmg = rolls["max"]
            if rolls["flinch_prob"] > 0.0:
                if (rolls["flinch_prob"] * 45.0 + rolls["avg"]) > (best_flinch_prob * 45.0 + flinch_move_dmg):
                    best_flinch_prob = rolls["flinch_prob"]
                    flinch_move_dmg = rolls["avg"]

        return {
            "max_dmg": max_dmg,
            "avg_dmg": avg_dmg,
            "best_move": best_move,
            "best_move_type": best_move_type,
            "prio_dmg": prio_max_dmg,
            "flinch_prob": best_flinch_prob,
            "flinch_dmg": flinch_move_dmg,
            "heal_amount": heal_amount,
            "has_roost": has_roost,
            "inflicts_status": inflicts_status,
        }

    # --------------------------------------------------------------------------
    # MEMORY SYNC & DYNAMIC LOADOUT DETECTION
    # --------------------------------------------------------------------------

    def _update_memory(self, obs: dict):
        turn = int(obs.get("turn", 1) or 1)
        if obs.get("team_preview") or turn <= 1 or (self.last_turn > 0 and turn < self.last_turn):
            self._reset_battle_memory()

        my_active = obs.get("my_active") or {}
        foe = obs.get("foe") or {}

        my_name = my_active.get("name", "")
        my_id = resolve_species(my_name)
        cond_info = parse_condition(my_active.get("condition", ""), float(my_active.get("hp_percent", 100) or 0))
        my_hp = cond_info["hp_pct"]

        valid_moves = obs.get("valid_moves") or []
        if my_id and len(valid_moves) >= 2:
            self.my_known_moves[my_id] = [dict(m) for m in valid_moves]

        foe_name = foe.get("name", "")
        foe_id = resolve_species(foe_name)
        foe_hp = float(foe.get("hp_percent", 100) or 0)
        foe_types = normalize_types(foe.get("types"), foe_id)

        if turn > self.last_turn and self.sand_turns > 0:
            self.sand_turns = max(0, self.sand_turns - 1)
        if primary_ability(foe_id, is_ours=False) == "Sand Stream" and foe_id != self.last_foe_id:
            self.sand_turns = 5

        if my_id != self.last_my_id or obs.get("force_switch"):
            self.my_tracked_boosts = {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}

        if foe_id != self.last_foe_id and primary_ability(foe_id, is_ours=False) == "Intimidate":
            if turn > 1 or self.last_turn <= 0:
                if primary_ability(my_id, is_ours=True) not in ("Clear Body", "Inner Focus", "Mirror Armor"):
                    self.my_tracked_boosts["atk"] = max(-6, self.my_tracked_boosts.get("atk", 0) - 1)

        if foe_id:
            if foe_id not in self.seen_foes:
                self.seen_foes[foe_id] = {
                    "name": foe_name,
                    "types": foe_types,
                    "hp_percent": foe_hp,
                    "status": foe.get("status", ""),
                    "boosts": foe.get("boosts", {}) or {},
                    "choice_scarf": False,
                    "spdef_mult": 1.0,
                    "def_mult": 1.0,
                }
            else:
                self.seen_foes[foe_id]["hp_percent"] = foe_hp
                self.seen_foes[foe_id]["types"] = foe_types
                self.seen_foes[foe_id]["status"] = foe.get("status", "")
                self.seen_foes[foe_id]["boosts"] = foe.get("boosts", {}) or {}

            if self.last_turn > 0 and not obs.get("force_switch"):
                if self.last_foe_id and foe_id != self.last_foe_id and self.last_foe_hp >= 40.0:
                    if self.last_expected_dmg < self.last_foe_hp:
                        self.opponent_mode = "SMART"

                if self.last_foe_id == foe_id and self.last_action_type == "move":
                    actual_foe_drop = self.last_foe_hp - foe_hp
                    actual_my_drop = self.last_my_hp - my_hp

                    if self.we_outsped_expected and self.last_expected_dmg >= self.last_foe_hp and foe_hp > 0 and actual_my_drop > 15:
                        self.seen_foes[foe_id]["choice_scarf"] = True

                    if self.last_expected_dmg >= 25.0 and 4.0 < actual_foe_drop < (self.last_expected_dmg * 0.72):
                        if self.last_move_cat == "Special":
                            self.seen_foes[foe_id]["spdef_mult"] = 1.5
                        elif self.last_move_cat == "Physical":
                            self.seen_foes[foe_id]["def_mult"] = 1.35

        if MY_TEAM_PROFILES.get(my_id, {}).get("item") == "Lum Berry" and cond_info["status"]:
            self.my_lum_intact = False

        self.last_turn = turn
        self.last_my_id = my_id
        self.last_foe_id = foe_id
        self.last_my_hp = my_hp
        self.last_foe_hp = foe_hp

    # --------------------------------------------------------------------------
    # UNIFIED 4-TURN SELF-AWARE DUEL ROLLOUT ENGINE (V9 MASTER)
    # --------------------------------------------------------------------------

    def _choose_best_single_turn_attack(
        self,
        my_name: str,
        my_types: list,
        my_stats: dict,
        my_status: str,
        my_hp: float,
        candidate_moves: list,
        foe_name: str,
        foe_types: list,
        foe_stats: dict,
        foe_status: str,
        foe_hp: float,
        foe_dmg: float,
        foe_prio_dmg: float,
        lum_available: bool = False,
    ) -> dict:
        best_res = {
            "mid": "", "rolls": {"min": 0.0, "avg": 0.0, "max": 0.0, "recoil_pct": 0.0, "drain_pct": 0.0},
            "prio": 0, "acc_w": 1.0, "lock": False, "self_drop": None, "moves_first": False,
        }
        best_val = -9999.0
        we_outspeed = (my_stats["spe"] > foe_stats["spe"])

        non_locking_can_ko = False
        for m in candidate_moves:
            mid = resolve_move(m)
            m_meta = MOVE_DB.get(mid, {})
            if m_meta.get("cat") == "Status" or m_meta.get("lock"):
                continue
            r = self._estimate_damage_rolls(
                my_name, my_types, my_stats, my_status,
                foe_name, foe_types, foe_stats, foe_hp,
                m, is_our_attack=True,
            )
            if r["min"] >= foe_hp:
                non_locking_can_ko = True
                break

        for m in candidate_moves:
            mid = resolve_move(m)
            m_meta = MOVE_DB.get(mid, {})
            cat = m.get("category") or m_meta.get("cat") or "Physical"
            if cat == "Status" or ((m.get("base_power") or 0) == 0 and m_meta.get("bp", 0) == 0):
                continue

            prio = int(m_meta.get("prio", 0))
            raw_acc = m.get("accuracy")
            acc = 100.0 if (raw_acc is True or raw_acc is None) else float(raw_acc or m_meta.get("acc", 100))
            acc_w = (acc / 100.0) ** 1.25

            moves_first = True if prio >= 2 else ((foe_prio_dmg < my_hp or we_outspeed) if prio > 0 else (we_outspeed and foe_prio_dmg < my_hp))
            rolls = self._estimate_damage_rolls(
                my_name, my_types, my_stats, my_status,
                foe_name, foe_types, foe_stats, foe_hp,
                m, is_our_attack=True,
            )

            if rolls["avg"] <= 0.0:
                val = -5000.0
            elif not moves_first and foe_dmg >= my_hp:
                # CRITICAL V9 FIX: If we move second and the foe KOs us this turn, a Priority 0 move
                # deals 0 actual damage! Penalize heavily so Priority moves (Extreme Speed / Bullet Punch)
                # are always chosen when in lethal range, while keeping a tiny tiebreaker among Priority 0 moves.
                val = -250.0 + min(2.5, rolls["avg"] * acc_w * 0.02)
            else:
                eff_dmg = min(foe_hp, rolls["avg"]) * acc_w
                val = eff_dmg + (rolls["drain_pct"] * 0.4) - (rolls["recoil_pct"] * 0.45)
                if rolls["min"] >= foe_hp:
                    val += 150.0 * acc_w + (prio * 28.0)
                    if moves_first:
                        val += 85.0
                    if (my_hp - rolls["recoil_pct"]) <= 0.0:
                        val -= 85.0  # Avoid self-KO from Life Orb + Rough Skin if a non-recoil KO exists

                if m_meta.get("lock"):
                    if non_locking_can_ko:
                        val -= 95.0
                    else:
                        val -= (14.0 if lum_available else 28.0)

                if m_meta.get("self_drop") and non_locking_can_ko and rolls["min"] >= foe_hp:
                    val -= 10.0

                if m_meta.get("two_turn"):
                    val -= 45.0

            if val > best_val:
                best_val = val
                best_res = {
                    "mid": mid,
                    "rolls": rolls,
                    "prio": prio,
                    "acc_w": acc_w,
                    "lock": bool(m_meta.get("lock")),
                    "self_drop": m_meta.get("self_drop"),
                    "moves_first": moves_first,
                }
        return best_res

    def _simulate_duel(
        self,
        my_name: str,
        my_types: list,
        my_boosts: dict,
        my_status: str,
        my_start_hp: float,
        candidate_moves: list,
        foe_name: str,
        foe_types: list,
        foe_stats: dict,
        foe_status: str,
        foe_start_hp: float,
        first_turn_move: dict = None,
        is_switch_in: bool = False,
        cur_active_name: str = "",
        cur_active_types: list = None,
        cur_active_stats: dict = None,
        cur_active_hp: float = 100.0,
        foe_boosts: dict = None,
    ) -> dict:
        my_id = resolve_species(my_name)
        my_prof = MY_TEAM_PROFILES.get(my_id, {})
        my_ability = primary_ability(my_id, is_ours=True)
        my_item = my_prof.get("item", "")
        foe_id = resolve_species(foe_name)
        foe_ability = primary_ability(foe_id, is_ours=False)

        sim_my_hp = float(my_start_hp)
        sim_foe_hp = float(foe_start_hp)
        sim_boosts = dict(my_boosts or {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0})
        sim_foe_boosts = dict(foe_boosts or {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0})
        sim_status = str(my_status or "")
        sim_lum = (my_item == "Lum Berry" and self.my_lum_intact and not sim_status)

        had_multiscale_at_start = (my_ability == "Multiscale" and my_start_hp >= 99.0)
        locked_move_dict = None
        locked_turns_left = 0
        used_pivot_with_boosts = False
        first_strike_ko = False
        turns_elapsed = 0
        resistance_pivot_bonus = 0.0
        tiebreaker_bonus = 0.0
        setup_flinch_penalty = 0.0
        discounted_foe_dmg_sum = 0.0
        hits_landed_on_foe = 0
        killed_via_priority_on_step_1 = False

        sand_active = (self.sand_turns > 0 or foe_ability == "Sand Stream")
        my_sand_chip = 6.25 if (sand_active and not any(t in ("Rock", "Ground", "Steel") for t in my_types) and my_ability != "Magic Guard") else 0.0

        # --- STEP 0: IF VOLUNTARY SWITCH, SIMULATE ENTRY TURN & FOE SELF-DROPS ---
        entry_dmg = 0.0
        if is_switch_in:
            turns_elapsed += 1
            sim_stats = self._estimate_stats(my_name, sim_boosts, sim_status, is_ours=True)
            cur_foe_stats = self._estimate_stats(foe_name, sim_foe_boosts, foe_status, is_ours=False)
            foe_direct = self._estimate_foe_threat(
                foe_name, foe_types, cur_foe_stats, foe_status,
                my_name, my_types, sim_stats, sim_my_hp,
            )
            if cur_active_name and cur_active_stats:
                foe_vs_cur = self._estimate_foe_threat(
                    foe_name, foe_types, cur_foe_stats, foe_status,
                    cur_active_name, cur_active_types or ["Normal"], cur_active_stats, cur_active_hp,
                )
                likely_mid = foe_vs_cur["best_move"]
                m_meta = MOVE_DB.get(likely_mid, {})
                if m_meta and m_meta.get("cat") != "Status":
                    rolls_on_sw = self._estimate_damage_rolls(
                        foe_name, foe_types, cur_foe_stats, foe_status,
                        my_name, my_types, sim_stats, sim_my_hp,
                        {"id": likely_mid, "name": likely_mid, "type": m_meta["type"], "category": m_meta["cat"], "base_power": m_meta["bp"]},
                        is_our_attack=False,
                    )
                    if my_ability == "Water Absorb" and m_meta.get("type") == "Water":
                        entry_dmg = -min(25.0, 100.0 - sim_my_hp)
                        resistance_pivot_bonus += 25.0
                    else:
                        if self.opponent_mode == "GREEDY":
                            entry_dmg = (0.85 * rolls_on_sw["avg"]) + (0.15 * foe_direct["avg_dmg"])
                        else:
                            entry_dmg = (0.55 * rolls_on_sw["avg"]) + (0.45 * foe_direct["avg_dmg"])

                        if rolls_on_sw["type_mult"] == 0.0:
                            resistance_pivot_bonus += 24.0
                        elif rolls_on_sw["type_mult"] <= 0.5:
                            resistance_pivot_bonus += 14.0
                        elif my_item == "Assault Vest" and m_meta.get("cat") == "Special" and entry_dmg < 42.0:
                            resistance_pivot_bonus += 16.0

                    if m_meta.get("self_drop") and rolls_on_sw["type_mult"] > 0.0:
                        for stat, delta in m_meta["self_drop"].items():
                            sim_foe_boosts[stat] = max(-6, sim_foe_boosts.get(stat, 0) + delta)
                else:
                    entry_dmg = foe_direct["avg_dmg"]
            else:
                entry_dmg = foe_direct["avg_dmg"]

            sim_my_hp = min(100.0, sim_my_hp - entry_dmg - my_sand_chip)
            if sim_my_hp <= 0.0:
                return {
                    "equity": -220.0 + sim_my_hp,
                    "wins_duel": False,
                    "my_end_hp": 0.0,
                    "foe_end_hp": sim_foe_hp,
                    "entry_dmg": entry_dmg,
                }

        # --- STEP 1: SIMULATE UP TO 4 COMBAT TURNS WITH TEMPORAL DISCOUNTING (gamma = 0.88^t) ---
        max_combat_steps = 3 if is_switch_in else 4
        for step in range(max_combat_steps):
            if sim_my_hp <= 0.0 or sim_foe_hp <= 0.0:
                break
            turns_elapsed += 1
            gamma = 0.88 ** step

            sim_stats = self._estimate_stats(my_name, sim_boosts, sim_status, is_ours=True)
            cur_foe_stats = self._estimate_stats(foe_name, sim_foe_boosts, foe_status, is_ours=False)
            foe_threat = self._estimate_foe_threat(
                foe_name, foe_types, cur_foe_stats, foe_status,
                my_name, my_types, sim_stats, sim_my_hp,
            )
            foe_dmg = foe_threat["max_dmg"] if (step == 0 and not is_switch_in) else foe_threat["avg_dmg"]
            foe_prio_dmg = foe_threat["prio_dmg"]
            we_outspeed = (sim_stats["spe"] > cur_foe_stats["spe"])

            if locked_turns_left > 0 and locked_move_dict is not None:
                chosen_move = locked_move_dict
            elif step == 0 and first_turn_move is not None:
                chosen_move = first_turn_move
            else:
                best_atk = self._choose_best_single_turn_attack(
                    my_name, my_types, sim_stats, sim_status, sim_my_hp,
                    candidate_moves, foe_name, foe_types, cur_foe_stats, foe_status,
                    sim_foe_hp, foe_dmg, foe_prio_dmg, lum_available=sim_lum,
                )
                chosen_move = {"id": best_atk["mid"], "name": best_atk["mid"]}

            mid = resolve_move(chosen_move)
            m_meta = MOVE_DB.get(mid, {})
            cat = chosen_move.get("category") or m_meta.get("cat") or ("Status" if (chosen_move.get("base_power") == 0 and m_meta.get("bp", 0) == 0) else "Physical")
            prio = int(m_meta.get("prio", 0))
            raw_acc = chosen_move.get("accuracy")
            acc = 100.0 if (raw_acc is True or raw_acc is None) else float(raw_acc or m_meta.get("acc", 100))
            acc_w = (acc / 100.0) ** 1.25

            moves_first = True if prio >= 2 else ((foe_prio_dmg < sim_my_hp or we_outspeed) if prio > 0 else (we_outspeed and foe_prio_dmg < sim_my_hp))

            # --- CASE A: STATUS / SETUP (Dragon Dance / Swords Dance) ---
            if cat == "Status" or (m_meta.get("bp", 0) == 0 and (chosen_move.get("base_power") or 0) == 0):
                if "boosts" in m_meta:
                    # STRICT V9 SETUP SAFETY FLOOR:
                    # 1. Never setup if starting HP < 65%
                    # 2. Never setup if statused without Lum Berry
                    if sim_my_hp < 65.0 or (sim_status in ("brn", "tox", "slp", "frz") and not sim_lum):
                        return {"equity": -250.0, "wins_duel": False, "my_end_hp": 0.0, "foe_end_hp": sim_foe_hp, "entry_dmg": entry_dmg}

                    if moves_first:
                        for k, v in m_meta["boosts"].items():
                            sim_boosts[k] = min(6, sim_boosts.get(k, 0) + v)
                        sim_stats = self._estimate_stats(my_name, sim_boosts, sim_status, is_ours=True)
                        foe_threat = self._estimate_foe_threat(
                            foe_name, foe_types, cur_foe_stats, foe_status,
                            my_name, my_types, sim_stats, sim_my_hp,
                        )
                        sim_my_hp -= foe_threat["max_dmg"]
                    else:
                        use_flinch_move = (foe_threat["flinch_prob"] >= 0.20 and foe_threat["flinch_dmg"] >= foe_dmg * 0.55)
                        incoming_hit = foe_threat["flinch_dmg"] if use_flinch_move else foe_dmg
                        effective_flinch_prob = foe_threat["flinch_prob"] if use_flinch_move else 0.0

                        sim_my_hp -= incoming_hit
                        if effective_flinch_prob > 0.0:
                            setup_flinch_penalty += (effective_flinch_prob * 90.0) + (effective_flinch_prob * incoming_hit)

                        for k, v in m_meta["boosts"].items():
                            sim_boosts[k] = min(6, sim_boosts.get(k, 0) + v)

                    # 3. Post-Setup Survival Buffer: Must retain >= 38% HP (>= 45% if holding Life Orb!)
                    min_safe_post_setup_hp = 45.0 if my_item == "Life Orb" else 38.0
                    if (sim_my_hp - my_sand_chip) < min_safe_post_setup_hp:
                        return {"equity": -240.0, "wins_duel": False, "my_end_hp": 0.0, "foe_end_hp": sim_foe_hp, "entry_dmg": entry_dmg}

                    if foe_threat["inflicts_status"] and sim_lum:
                        sim_lum = False
                elif "heal" in m_meta:
                    if moves_first:
                        sim_my_hp = min(100.0, sim_my_hp + float(m_meta["heal"])) - foe_dmg
                    else:
                        sim_my_hp -= foe_dmg
                        if sim_my_hp <= 0.0:
                            break
                        sim_my_hp = min(100.0, sim_my_hp + float(m_meta["heal"]))
                else:
                    sim_my_hp -= foe_dmg

                if foe_threat["best_move"] in MOVE_DB and MOVE_DB[foe_threat["best_move"]].get("self_drop"):
                    for stat, delta in MOVE_DB[foe_threat["best_move"]]["self_drop"].items():
                        sim_foe_boosts[stat] = max(-6, sim_foe_boosts.get(stat, 0) + delta)

                sim_my_hp -= my_sand_chip
                continue

            # --- CASE B: DAMAGING ATTACK ---
            rolls = self._estimate_damage_rolls(
                my_name, my_types, sim_stats, sim_status,
                foe_name, foe_types, cur_foe_stats, sim_foe_hp,
                chosen_move, is_our_attack=True,
            )
            if rolls["avg"] <= 0.0:
                return {"equity": -300.0, "wins_duel": False, "my_end_hp": 0.0, "foe_end_hp": sim_foe_hp, "entry_dmg": entry_dmg}

            if m_meta.get("pivot") and (sim_boosts.get("atk", 0) > 0 or sim_boosts.get("spa", 0) > 0 or sim_boosts.get("spe", 0) > 0):
                used_pivot_with_boosts = True

            if moves_first:
                dealt = rolls["min"] if (rolls["min"] >= sim_foe_hp and acc >= 95.0) else (rolls["avg"] * acc_w)
                actual_removed = min(sim_foe_hp, dealt)
                discounted_foe_dmg_sum += actual_removed * gamma
                sim_foe_hp -= dealt
                hits_landed_on_foe += 1
                sim_my_hp = min(100.0, sim_my_hp + rolls["drain_pct"] - rolls["recoil_pct"])

                if m_meta.get("lock") and locked_turns_left == 0:
                    locked_move_dict = chosen_move
                    locked_turns_left = 2
                elif locked_turns_left > 0:
                    locked_turns_left -= 1
                    if locked_turns_left == 0 and sim_lum:
                        sim_lum = False

                if sim_foe_hp <= 0.0 or sim_my_hp <= 0.0:
                    if sim_foe_hp <= 0.0 and sim_my_hp > 0.0:
                        if step == 0 and not is_switch_in:
                            first_strike_ko = True
                        elif step == 1 and not is_switch_in and prio > 0 and hits_landed_on_foe == 2:
                            killed_via_priority_on_step_1 = True
                    break

                if foe_threat["heal_amount"] >= 50.0 and sim_foe_hp <= 55.0 and dealt < 46.0:
                    healed = min(100.0 - sim_foe_hp, foe_threat["heal_amount"])
                    sim_foe_hp += healed
                    discounted_foe_dmg_sum -= healed * gamma * 0.75
                else:
                    sim_my_hp -= foe_dmg
                    if foe_threat["best_move"] in MOVE_DB and MOVE_DB[foe_threat["best_move"]].get("self_drop"):
                        for stat, delta in MOVE_DB[foe_threat["best_move"]]["self_drop"].items():
                            sim_foe_boosts[stat] = max(-6, sim_foe_boosts.get(stat, 0) + delta)
            else:
                use_flinch_move = (foe_threat["flinch_prob"] >= 0.20 and foe_threat["flinch_dmg"] >= foe_dmg * 0.55)
                incoming_hit = foe_threat["flinch_dmg"] if use_flinch_move else foe_dmg
                effective_flinch_prob = foe_threat["flinch_prob"] if use_flinch_move else 0.0

                active_foe_types = list(foe_types)
                if foe_threat["heal_amount"] >= 50.0 and sim_foe_hp <= 62.0 and (rolls["avg"] * (1.0 - effective_flinch_prob)) < 52.0:
                    healed = min(100.0 - sim_foe_hp, foe_threat["heal_amount"])
                    sim_foe_hp += healed
                    discounted_foe_dmg_sum -= healed * gamma * 0.75
                    effective_flinch_prob = 0.0
                    if foe_threat["has_roost"] and "Flying" in active_foe_types:
                        active_foe_types = [t for t in active_foe_types if t != "Flying"] or ["Normal"]
                else:
                    sim_my_hp -= incoming_hit
                    if foe_threat["best_move"] in MOVE_DB and MOVE_DB[foe_threat["best_move"]].get("self_drop"):
                        for stat, delta in MOVE_DB[foe_threat["best_move"]]["self_drop"].items():
                            sim_foe_boosts[stat] = max(-6, sim_foe_boosts.get(stat, 0) + delta)

                # If we faint before moving, we deal 0 damage!
                # Only apply a tiny micro-tiebreaker (max +2.5) to distinguish Outrage from Fire Punch
                # when no priority move is available (e.g. vs Ghost-type Dragapult).
                if sim_my_hp <= 0.0:
                    if step == 0 and not is_switch_in:
                        tiebreaker_bonus = min(2.5, rolls["avg"] * acc_w * 0.02)
                    break

                if m_meta.get("lock") and locked_turns_left == 0:
                    locked_move_dict = chosen_move
                    locked_turns_left = 2
                elif locked_turns_left > 0:
                    locked_turns_left -= 1
                    if locked_turns_left == 0 and sim_lum:
                        sim_lum = False

                rolls_after_foe = self._estimate_damage_rolls(
                    my_name, my_types, sim_stats, sim_status,
                    foe_name, active_foe_types, cur_foe_stats, sim_foe_hp,
                    chosen_move, is_our_attack=True,
                )
                dealt = (
                    rolls_after_foe["min"]
                    if (rolls_after_foe["min"] >= sim_foe_hp and effective_flinch_prob == 0.0 and acc >= 95.0)
                    else (rolls_after_foe["avg"] * acc_w)
                ) * (1.0 - effective_flinch_prob)
                actual_removed = min(sim_foe_hp, dealt)
                discounted_foe_dmg_sum += actual_removed * gamma
                sim_foe_hp -= dealt
                hits_landed_on_foe += 1
                sim_my_hp = min(100.0, sim_my_hp + (rolls_after_foe["drain_pct"] - rolls_after_foe["recoil_pct"]) * (1.0 - effective_flinch_prob))

                if sim_foe_hp <= 0.0 or sim_my_hp <= 0.0:
                    break

            if m_meta.get("self_drop"):
                for stat, delta in m_meta["self_drop"].items():
                    sim_boosts[stat] = max(-6, sim_boosts.get(stat, 0) + delta)

            sim_my_hp -= my_sand_chip
            if m_meta.get("pivot") and step == 0:
                break

        # --- STEP 2: UNIFIED NET MATCH EQUITY ---
        sim_my_hp = max(0.0, sim_my_hp)
        sim_foe_hp = max(0.0, sim_foe_hp)

        foe_hp_eliminated = foe_start_hp - sim_foe_hp
        my_hp_lost = my_start_hp - sim_my_hp

        effective_foe_prog = (0.65 * foe_hp_eliminated) + (0.50 * discounted_foe_dmg_sum)
        equity = effective_foe_prog - (my_hp_lost * 1.12) + resistance_pivot_bonus + tiebreaker_bonus - setup_flinch_penalty

        if sim_foe_hp <= 0.0 and sim_my_hp > 0.0:
            equity += 65.0
            if first_strike_ko:
                equity += 22.0
            elif killed_via_priority_on_step_1:
                equity += 20.0
            equity -= (turns_elapsed * 4.0)
        elif sim_my_hp <= 0.0 and sim_foe_hp > 0.0:
            equity -= 75.0
        elif sim_my_hp <= 0.0 and sim_foe_hp <= 0.0:
            equity -= 38.0

        net_off_boosts = max(0, sim_boosts.get("atk", 0)) + max(0, sim_boosts.get("spa", 0)) + max(0, sim_boosts.get("spe", 0))
        if had_multiscale_at_start and sim_my_hp < 99.0:
            if sim_foe_hp <= 0.0 and sim_my_hp >= 42.0 and net_off_boosts >= 2 and setup_flinch_penalty == 0.0:
                equity -= 6.0
            else:
                equity -= 26.0

        if locked_turns_left > 0 and sim_my_hp > 0.0:
            equity -= (18.0 if sim_lum else 34.0)

        if used_pivot_with_boosts:
            equity -= 90.0
        elif sim_foe_hp <= 0.0 and sim_my_hp > 40.0 and net_off_boosts > 0:
            equity += min(34.0, net_off_boosts * 12.0 * (sim_my_hp / 100.0))

        return {
            "equity": equity,
            "wins_duel": (sim_foe_hp <= 0.0 and sim_my_hp >= 8.0),
            "my_end_hp": sim_my_hp,
            "foe_end_hp": sim_foe_hp,
            "entry_dmg": entry_dmg,
        }

    # --------------------------------------------------------------------------
    # MUTUAL-KO BLIND SWITCH EVALUATOR
    # --------------------------------------------------------------------------

    def _evaluate_blind_switch(self, sw: dict) -> float:
        s_name = sw.get("name", "")
        s_id = resolve_species(s_name)
        s_hp = float(sw.get("hp_percent", 100) or 0)
        if s_hp <= 0:
            return -9999.0

        s_types = normalize_types(sw.get("types"), s_id)
        s_moves = self.my_known_moves.get(s_id) or [{"id": mid, "name": mid} for mid in ROSTER_DB.get(s_id, {}).get("moves", [])]

        living_seen = [
            (fid, fdata) for fid, fdata in self.seen_foes.items()
            if fid != self.last_foe_id and fdata.get("hp_percent", 0) > 0
        ]
        if living_seen:
            total_eq = 0.0
            for fid, fdata in living_seen:
                f_stats = self._estimate_stats(fdata.get("name", fid), fdata.get("boosts"), fdata.get("status", ""), is_ours=False)
                sim = self._simulate_duel(
                    s_name, s_types, {}, "", s_hp, s_moves,
                    fdata.get("name", fid), fdata.get("types", ["Normal"]), f_stats,
                    fdata.get("status", ""), float(fdata.get("hp_percent", 100)),
                    is_switch_in=False,
                )
                total_eq += sim["equity"]
            return total_eq / len(living_seen)

        quad_weaknesses = 0
        for atk_type in TYPE_CHART:
            if get_type_effectiveness(atk_type, s_types) >= 4.0:
                quad_weaknesses += 1

        score = s_hp - (quad_weaknesses * 35.0)
        my_prof = MY_TEAM_PROFILES.get(s_id, {})
        if my_prof.get("item") == "Assault Vest":
            score += 28.0
        if primary_ability(s_id, is_ours=True) == "Multiscale" and s_hp >= 99.0:
            score += 32.0
        return score

    # --------------------------------------------------------------------------
    # MASTER DECISION INTERFACE
    # --------------------------------------------------------------------------

    def _choose_team_preview(self, obs: dict) -> str:
        my_team = obs.get("my_team") or []
        foe = obs.get("foe") or {}
        foe_name = foe.get("name", "")
        foe_id = resolve_species(foe_name)

        if len(my_team) < 3 or not foe_id:
            return "team 123"

        foe_types = normalize_types(foe.get("types"), foe_id)
        foe_stats = self._estimate_stats(foe_name, is_ours=False)

        best_slot = 1
        best_equity = -9999.0
        for idx, member in enumerate(my_team[:3], start=1):
            m_name = member.get("name", "")
            m_id = resolve_species(m_name)
            m_types = normalize_types(member.get("types"), m_id)
            m_moves = self.my_known_moves.get(m_id) or [{"id": mid, "name": mid} for mid in ROSTER_DB.get(m_id, {}).get("moves", [])]
            sim = self._simulate_duel(
                m_name, m_types, {}, "", 100.0, m_moves,
                foe_name, foe_types, foe_stats, "", 100.0,
                is_switch_in=False,
            )
            if sim["equity"] > best_equity:
                best_equity = sim["equity"]
                best_slot = idx

        other_slots = [s for s in (1, 2, 3) if s != best_slot]
        return f"team {best_slot}{other_slots[0]}{other_slots[1]}"

    def decide(self, observation: dict) -> str:
        try:
            if not isinstance(observation, dict):
                return "move 1"

            prev_action_type = self.last_action_type
            prev_switch_foe = self.last_voluntary_switch_foe
            self._update_memory(observation)

            if observation.get("team_preview"):
                return self._choose_team_preview(observation)

            valid_switches = observation.get("valid_switches") or []
            valid_moves = observation.get("valid_moves") or []

            my_active = observation.get("my_active") or {}
            foe = observation.get("foe") or {}

            my_name = my_active.get("name", "")
            my_id = resolve_species(my_name)
            my_types = normalize_types(my_active.get("types"), my_id)
            cond_info = parse_condition(my_active.get("condition", ""), float(my_active.get("hp_percent", 100) or 0))
            my_hp = cond_info["hp_pct"]
            my_status = cond_info["status"]
            my_boosts = self._get_effective_my_boosts(my_active.get("boosts"))
            my_stats = self._estimate_stats(
                my_name, my_boosts, my_status, is_ours=True,
                raw_stats=my_active.get("stats"), parsed_max_hp=cond_info["max_hp"],
            )

            foe_name = foe.get("name", "")
            foe_id = resolve_species(foe_name)
            foe_types = normalize_types(foe.get("types"), foe_id)
            foe_hp = float(foe.get("hp_percent", 0) or 0)
            foe_boosts = foe.get("boosts") or {}
            foe_status = str(foe.get("status", "") or "")
            foe_stats = self._estimate_stats(foe_name, foe_boosts, foe_status, is_ours=False)

            # 1. Forced Switch Phase
            if observation.get("force_switch"):
                if valid_switches:
                    best_sw = valid_switches[0]
                    best_sw_eq = -9999.0
                    for s in valid_switches:
                        s_name = s.get("name", "")
                        s_id = resolve_species(s_name)
                        s_hp = float(s.get("hp_percent", 100) or 0)
                        if s_hp <= 0:
                            continue
                        if foe_hp <= 0.0:
                            eq = self._evaluate_blind_switch(s)
                        else:
                            s_types = normalize_types(s.get("types"), s_id)
                            s_moves = self.my_known_moves.get(s_id) or [{"id": mid, "name": mid} for mid in ROSTER_DB.get(s_id, {}).get("moves", [])]
                            sim = self._simulate_duel(
                                s_name, s_types, {}, "", s_hp, s_moves,
                                foe_name, foe_types, foe_stats, foe_status, foe_hp,
                                is_switch_in=False, foe_boosts=foe_boosts,
                            )
                            eq = sim["equity"]
                        if eq > best_sw_eq:
                            best_sw_eq = eq
                            best_sw = s
                    self.last_action_type = "forced_switch"
                    return f"switch {best_sw['index']}"
                return "pass"

            if not valid_moves:
                if valid_switches:
                    self.last_action_type = "voluntary_switch"
                    self.last_voluntary_switch_foe = foe_id
                    return f"switch {valid_switches[0]['index']}"
                return "move 1"

            if foe_hp <= 0.0:
                foe_hp = 100.0

            # 2. Evaluate All Legal Stay-In Moves via 4-Turn Temporally Discounted Rollout
            best_move = valid_moves[0]
            best_move_equity = -9999.0
            best_move_id = ""
            best_move_expected_dmg = 0.0
            best_move_cat = "Physical"
            best_move_outspeeds = (my_stats["spe"] > foe_stats["spe"])

            best_raw_attack_equity = -9999.0
            can_already_ohko = False
            for m in valid_moves:
                mid = resolve_move(m)
                m_meta = MOVE_DB.get(mid, {})
                cat = m.get("category") or m_meta.get("cat") or "Physical"
                if cat != "Status" and ((m.get("base_power") or 0) > 0 or m_meta.get("bp", 0) > 0):
                    r = self._estimate_damage_rolls(
                        my_name, my_types, my_stats, my_status,
                        foe_name, foe_types, foe_stats, foe_hp,
                        m, is_our_attack=True,
                    )
                    if r["min"] >= foe_hp:
                        can_already_ohko = True
                    sim_atk = self._simulate_duel(
                        my_name, my_types, my_boosts, my_status, my_hp, valid_moves,
                        foe_name, foe_types, foe_stats, foe_status, foe_hp,
                        first_turn_move=m, is_switch_in=False, foe_boosts=foe_boosts,
                    )
                    if sim_atk["equity"] > best_raw_attack_equity:
                        best_raw_attack_equity = sim_atk["equity"]

            for m in valid_moves:
                mid = resolve_move(m)
                m_meta = MOVE_DB.get(mid, {})
                cat = m.get("category") or m_meta.get("cat") or "Physical"
                is_status = (cat == "Status" or ((m.get("base_power") or 0) == 0 and m_meta.get("bp", 0) == 0))

                sim = self._simulate_duel(
                    my_name, my_types, my_boosts, my_status, my_hp, valid_moves,
                    foe_name, foe_types, foe_stats, foe_status, foe_hp,
                    first_turn_move=m, is_switch_in=False, foe_boosts=foe_boosts,
                )
                eq = sim["equity"]

                if is_status and "boosts" in m_meta:
                    already_boosted = (my_boosts.get("atk", 0) >= 1 or my_boosts.get("spa", 0) >= 1)
                    if (
                        my_hp < 65.0
                        or can_already_ohko
                        or already_boosted
                        or not sim["wins_duel"]
                        or eq < best_raw_attack_equity + 12.0
                    ):
                        eq = -500.0

                if eq > best_move_equity:
                    best_move_equity = eq
                    best_move = m
                    best_move_id = mid
                    best_move_cat = "Status" if is_status else str(cat).strip().capitalize()
                    rolls = self._estimate_damage_rolls(
                        my_name, my_types, my_stats, my_status,
                        foe_name, foe_types, foe_stats, foe_hp,
                        m, is_our_attack=True,
                    )
                    best_move_expected_dmg = rolls["avg"]
                    prio = int(m_meta.get("prio", 0))
                    best_move_outspeeds = True if prio > 0 else (my_stats["spe"] > foe_stats["spe"])

            # 3. Evaluate Voluntary Switches
            just_voluntarily_switched_same_foe = (
                prev_action_type == "voluntary_switch" and prev_switch_foe == foe_id
            )

            if valid_switches and not just_voluntarily_switched_same_foe:
                best_sw = None
                best_sw_sim = None
                best_sw_equity = -9999.0

                for s in valid_switches:
                    s_name = s.get("name", "")
                    s_id = resolve_species(s_name)
                    s_hp = float(s.get("hp_percent", 100) or 0)
                    if s_hp <= 0:
                        continue
                    s_types = normalize_types(s.get("types"), s_id)
                    s_moves = self.my_known_moves.get(s_id) or [{"id": mid, "name": mid} for mid in ROSTER_DB.get(s_id, {}).get("moves", [])]

                    sim_sw = self._simulate_duel(
                        s_name, s_types, {}, "", s_hp, s_moves,
                        foe_name, foe_types, foe_stats, foe_status, foe_hp,
                        is_switch_in=True,
                        cur_active_name=my_name, cur_active_types=my_types,
                        cur_active_stats=my_stats, cur_active_hp=my_hp,
                        foe_boosts=foe_boosts,
                    )
                    if sim_sw["equity"] > best_sw_equity:
                        best_sw_equity = sim_sw["equity"]
                        best_sw = s
                        best_sw_sim = sim_sw

                if best_sw is not None and best_sw_sim["wins_duel"]:
                    is_low_hp_fodder = (my_hp <= 30.0 and not best_move_outspeeds and best_move_equity < -40.0)
                    if is_low_hp_fodder:
                        if best_sw_sim["entry_dmg"] < 30.0 and best_sw_equity > best_move_equity + 30.0:
                            self.last_action_type = "voluntary_switch"
                            self.last_voluntary_switch_foe = foe_id
                            return f"switch {best_sw['index']}"
                    elif best_sw_equity > best_move_equity + 18.0:
                        self.last_action_type = "voluntary_switch"
                        self.last_voluntary_switch_foe = foe_id
                        return f"switch {best_sw['index']}"

            # 4. Commit to Best Move & Track Self Boosts/Drops
            if best_move_id in MOVE_DB and "boosts" in MOVE_DB[best_move_id]:
                for stat, delta in MOVE_DB[best_move_id]["boosts"].items():
                    self.my_tracked_boosts[stat] = min(6, self.my_tracked_boosts.get(stat, 0) + delta)
            elif best_move_id in MOVE_DB and "self_drop" in MOVE_DB[best_move_id]:
                for stat, delta in MOVE_DB[best_move_id]["self_drop"].items():
                    self.my_tracked_boosts[stat] = max(-6, self.my_tracked_boosts.get(stat, 0) + delta)

            self.last_action_type = "move"
            self.last_voluntary_switch_foe = None
            self.last_move_id = best_move_id
            self.last_expected_dmg = best_move_expected_dmg
            self.last_move_cat = best_move_cat
            self.we_outsped_expected = best_move_outspeeds

            return f"move {best_move.get('index', 1)}"

        except Exception:
            valid_moves = observation.get("valid_moves", []) if isinstance(observation, dict) else []
            if valid_moves:
                foe = (observation.get("foe") or {}) if isinstance(observation, dict) else {}
                foe_id = resolve_species(foe.get("name", ""))
                foe_types = normalize_types(foe.get("types"), foe_id)
                best_fallback = max(
                    valid_moves,
                    key=lambda m: (m.get("base_power") or 0)
                    * get_type_effectiveness(m.get("type", "Normal"), foe_types)
                    * (1.5 if m.get("stab") else 1.0),
                )
                return f"move {best_fallback.get('index', 1)}"
            valid_switches = observation.get("valid_switches", []) if isinstance(observation, dict) else []
            if valid_switches:
                return f"switch {valid_switches[0].get('index', 2)}"
            return "move 1"