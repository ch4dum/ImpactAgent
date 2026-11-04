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

# Inventory display name (lowercase) -> grenade type.
GRENADE_ITEM_TYPES = {
    "flashbang": "flash",
    "smoke grenade": "smoke",
    "high explosive grenade": "he",
    "molotov": "molotov",
    "incendiary grenade": "molotov",
    "decoy grenade": "decoy",
}

# A grenade thrown this long before death can still show in the inventory (and as active
# weapon) at death. Leetify does not count it as unused utility.
THROWN_GRENADE_GRACE_SECONDS = 1.0

# Damage weapons that count as utility damage.
HE_DAMAGE_WEAPONS = {"hegrenade"}
FIRE_DAMAGE_WEAPONS = {"inferno", "molotov", "incgrenade"}
NON_GUN_WEAPONS = {"knife", "knife_t", "bayonet", "taser", "c4", "world", "worldspawn"} | set(GRENADE_WEAPONS) | FIRE_DAMAGE_WEAPONS

# Leetify: enemies blinded for less than this are ignored.
MIN_BLIND_SECONDS = 1.1

# Trade window in seconds. NOT published by Leetify. KAST + traded deaths + trade kills
# (succeeded) on inferno-44a522c3 + mirage-65db631a bound it to [3.48, 4.47) s; 4.0 is inside.
TRADE_WINDOW_SECONDS = 4.0

# ---- parse safety (user uploads)
# Max size of a demo after decompression (and of a plain .dem). Real demos are 80-330 MB.
MAX_DEMO_BYTES = 1 << 30  # 1 GiB
# Wall-clock limit for parsing one demo (runs in a child process that is killed on timeout).
# A 180 MB demo takes ~10-15 s.
PARSE_TIMEOUT_SECONDS = 300

# Trade attempt = damaged the killer, or fired while the killer was spotted and the crosshair
# was within this angle of him. HYPOTHESIS (best of a grid search on 2 matches, spec §3).
TRADE_ATTEMPT_AIM_DEG = 20.0
