"""Game constants. Values marked VERIFY should be checked against items_game."""

TEAM_T = 2
TEAM_CT = 3
SIDE_BY_TEAM_NUM = {TEAM_T: "T", TEAM_CT: "CT"}

DEFAULT_TICKRATE = 64

# Round / bomb timers for wp_states time_left_s (impact-spec §2.1). Read from server_cvar
# (mp_roundtime, mp_c4timer) when present; these are the CS2 competitive defaults (seconds).
ROUND_TIME_S = 115.0
C4_TIMER_S = 40.0

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
# Molotov damage metric = fire only. The bottle hitting a player ("molotov" / "incgrenade", 1 HP)
# is not counted (dust2-85507dfb: gxmxi r14, 54 -> 53).
MOLOTOV_FIRE_WEAPONS = {"inferno"}
NON_GUN_WEAPONS = {"knife", "knife_t", "bayonet", "taser", "c4", "world", "worldspawn"} | set(GRENADE_WEAPONS) | FIRE_DAMAGE_WEAPONS

# Leetify: enemies blinded for less than this are ignored.
MIN_BLIND_SECONDS = 1.1

# Trade window in seconds. NOT published by Leetify. KAST + traded deaths + trade kills
# (succeeded) on inferno-44a522c3 + mirage-65db631a bound it to [3.48, 4.47) s; 4.0 is inside.
TRADE_WINDOW_SECONDS = 4.0

# ---- round buy types (our own definition, spec §8 / data-model §2.2)
BUY_TYPE_PISTOL = "pistol"
BUY_TYPE_ECO = "eco"
BUY_TYPE_SEMI_ECO = "semi-eco"
BUY_TYPE_FORCE = "force"
BUY_TYPE_FULL = "full"

BUY_THRESHOLD_ECO_MAX = 1500       # < $1,500 is eco
BUY_THRESHOLD_SEMI_ECO_MAX = 2500  # $1,500 - $2,499 is semi-eco
BUY_THRESHOLD_FORCE_MAX = 3900     # $2,500 - $3,899 is force, >= $3,900 is full

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
# Target point layouts: (fraction of eye height, extra z, sideways offset perpendicular to the
# observer's line of sight). Points are tried in order; the first clear ray = seen.
_F = TARGET_FEET_OFFSET
TARGET_LAYOUTS = {
    "3": [(1.0, 0, 0), (TARGET_CHEST_FRACTION, 0, 0), (0, _F, 0)],
    "8": [(1.0, 0, 0), (0.85, 0, 0), (TARGET_CHEST_FRACTION, 0, 0), (0.5, 0, 0), (0.25, 0, 0), (0, _F, 0),
          (0.8, 0, 14), (0.8, 0, -14)],
    "24": [(1.0, 0, 0), (0.9, 0, 0), (0.8, 0, 0), (0.7, 0, 0), (0.6, 0, 0), (0.45, 0, 0), (0.3, 0, 0), (0, _F, 0),
           (1.0, 0, 5), (1.0, 0, -5), (0.85, 0, 10), (0.85, 0, -10), (0.8, 0, 16), (0.8, 0, -16),
           (0.65, 0, 16), (0.65, 0, -16), (0.5, 0, 12), (0.5, 0, -12), (0.35, 0, 8), (0.35, 0, -8),
           (0.2, 0, 8), (0.2, 0, -8), (0, _F, 8), (0, _F, -8)],
}
TARGET_LAYOUT = "8"  # 8 vs 24 points (dense capsule): TTD bias -125/-83/-105 vs -139/-70/-95 ms (inferno/mirage/dust2), 24 = ~2.7x rays
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

# ---- aim (impactagent/parse/aim.py, impactagent/metrics/aim.py, spec §1)
# Weapon classes (demo weapon names without "weapon_").
RIFLES = {"ak47", "m4a1", "m4a1_silencer", "famas", "galilar", "aug", "sg556"}
SNIPERS = {"awp", "ssg08", "scar20", "g3sg1"}
SMGS = {"mp9", "mac10", "mp7", "mp5sd", "ump45", "p90", "bizon"}
PISTOLS = {"glock", "hkp2000", "usp_silencer", "p250", "elite", "fiveseven", "tec9", "cz75a", "deagle", "revolver"}
SHOTGUNS = {"nova", "xm1014", "sawedoff", "mag7"}
MACHINE_GUNS = {"m249", "negev"}
GUNS = RIFLES | SNIPERS | SMGS | PISTOLS | SHOTGUNS | MACHINE_GUNS
# Weapons whose shots / hits feed the aim tables. Taser counts in shots_fired (dust2-85507dfb: mojo
# 1 taser shot = the missing shot); whether a taser HIT counts is unknown (no taser hit yet).
AIM_WEAPONS = GUNS | {"taser"}
# Max running speed (units/s, unscoped) per weapon, CS2 items_game (VERIFY).
WEAPON_MAX_SPEED = {
    "ak47": 215, "m4a1": 225, "m4a1_silencer": 225, "famas": 220, "galilar": 215, "aug": 220, "sg556": 210,
    "awp": 200, "ssg08": 230, "scar20": 215, "g3sg1": 215,
    "glock": 240, "hkp2000": 240, "usp_silencer": 240, "p250": 240, "elite": 240, "fiveseven": 240,
    "tec9": 240, "cz75a": 240, "deagle": 230, "revolver": 220,
    "mp9": 240, "mac10": 240, "mp7": 220, "mp5sd": 235, "ump45": 230, "p90": 230, "bizon": 240,
    "nova": 220, "xm1014": 215, "sawedoff": 210, "mag7": 225, "m249": 195, "negev": 150,
}
# Counter-strafe: a rifle shot at a seen enemy, not ducking, is "good" below this × max speed.
COUNTER_STRAFE_SPEED_FRACTION = 0.34
# Spray = shots of one weapon with <= this gap between shots; sprays need >= SPRAY_MIN_SHOTS.
SPRAY_MAX_GAP_SECONDS = 0.25
SPRAY_MIN_SHOTS = 3
SPRAY_FIRST_COUNTED_SHOT = 2  # 0-based: spray accuracy counts the 3rd bullet on (HYPOTHESIS)
# First bullet = a shot after at least this long without shooting (HYPOTHESIS).
FIRST_BULLET_GAP_SECONDS = 0.5
# Engagement: A sees B continuously (gaps <= ENGAGEMENT_GAP_TICKS) before damaging him;
# first_seen is searched back at most ENGAGEMENT_LOOKBACK_SECONDS.
ENGAGEMENT_GAP_TICKS = 8
ENGAGEMENT_LOOKBACK_SECONDS = 2.5
TTD_MAX_SECONDS = 1.0  # time to damage / crosshair placement drop engagements at or over this
