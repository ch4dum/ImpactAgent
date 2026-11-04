"""Game constants. Values marked VERIFY should be checked against items_game."""

TEAM_T = 2
TEAM_CT = 3
SIDE_BY_TEAM_NUM = {TEAM_T: "T", TEAM_CT: "CT"}

DEFAULT_TICKRATE = 64

GRENADE_WEAPONS = {
    "flashbang": "flash",
    "smokegrenade": "smoke",
    "hegrenade": "he",
    "molotov": "molotov",
    "incgrenade": "molotov",  # Leetify counts molotov + incendiary together
    "decoy": "decoy",
}

# Grenade prices in $ (VERIFY incendiary price for CS2).
GRENADE_PRICES = {
    "flashbang": 200,
    "smoke grenade": 300,
    "high explosive grenade": 300,
    "molotov": 400,
    "incendiary grenade": 500,
    "decoy grenade": 50,
}

# Damage weapons that count as utility damage.
HE_DAMAGE_WEAPONS = {"hegrenade"}
FIRE_DAMAGE_WEAPONS = {"inferno", "molotov", "incgrenade"}
NON_GUN_WEAPONS = {"knife", "knife_t", "bayonet", "taser", "c4", "world", "worldspawn"} | set(GRENADE_WEAPONS) | FIRE_DAMAGE_WEAPONS

# Leetify: enemies blinded for less than this are ignored.
MIN_BLIND_SECONDS = 1.1

# Trade window in seconds. NOT published by Leetify — calibrate with data/validation.
TRADE_WINDOW_SECONDS = 5.0
