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

# ---- visibility (impactagent/visibility, spec §0)
# Eye z = origin z + EYE_HEIGHT_STANDING + m_flDuckViewOffset (0 standing .. -18 crouched).
# The demo does not network m_vecViewOffset, so only the 64 standing base is a constant.
EYE_HEIGHT_STANDING = 64.0
# Target points on the other player: head (= his eye height), chest, feet. Any clear ray = seen.
TARGET_CHEST_FRACTION = 0.72  # chest z as a fraction of eye height
TARGET_FEET_OFFSET = 8.0  # above origin, so the ray does not graze the floor
# Lag compensation: the target counts as seen if his position at any of the last N ticks is
# in sight. The needed rewind does NOT follow the observer's ping (rank corr 0.01 on 64 hits
# in 2 matches), so a fixed window is used. 7 = largest rewind the 224 normal kills needed.
LAG_COMP_WINDOW_TICKS = 7
# Field of view: max angle (deg) between the view direction and a target point. Half-angle:
# CS2 at 16:9 is ~53 deg horizontally, 4:3 is 45.
VISIBILITY_FOV_DEG = 50.0
# Smoke = sphere at the smokegrenade_detonate position + z offset, blocking from detonate + bloom
# until smokegrenade_expired (or detonate + duration if the round ends first). Grid search on
# inferno (R 96-160, z 0-64, bloom 0-1.5 s): 144 / 32 / 0.5 keeps 72/72 normal kills seen and
# blocks 7/7 through-smoke kills; mirage holdout 150/152 and 5/7. Bloom 0 blocks kills just
# after the pop (smoke not grown yet).
SMOKE_RADIUS = 144.0
SMOKE_CENTER_Z_OFFSET = 32.0
SMOKE_BLOOM_SECONDS = 0.5
SMOKE_DURATION_SECONDS = 22.0625  # detonate -> expired, same for all 28 paired smokes in inferno
