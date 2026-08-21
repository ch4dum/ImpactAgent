import pandas as pd
from src.analyzer.schemas import FullMatchFaceitMetrics

def print_faceit_dashboard(metrics: FullMatchFaceitMetrics, target_player: str = None):
    print("\n" + "="*80)
    print(f" 🏆 IMPACTAGENT - FACEIT MATCH STATS DASHBOARD ({metrics.map_name.upper()} | {metrics.total_rounds} ROUNDS)")
    print("="*80)

    # Table 1: GENERAL STATS
    print("\n📊 1. GENERAL STATS")
    gen_rows = []
    for p, g in metrics.general.items():
        gen_rows.append({
            "Player": f"⭐ {p}" if p == target_player else p,
            "K": g.kills,
            "D": g.deaths,
            "A": g.assists,
            "K/D": g.kd_ratio,
            "K/R": g.kr_ratio,
            "KDA": g.kda,
            "HS Kills": g.hs_kills,
            "HS %": f"{g.hs_percent:.1f}%"
        })
    df_gen = pd.DataFrame(gen_rows)
    print(df_gen.to_string(index=False))

    # Table 2: ADVANCED STATS
    print("\n⚡ 2. ADVANCE STATS")
    adv_rows = []
    for p, a in metrics.advanced.items():
        adv_rows.append({
            "Player": f"⭐ {p}" if p == target_player else p,
            "Total Shots": a.total_shots,
            "Counter-Strafe Acc %": f"{a.counter_strafe_accuracy_percent}%",
            "KAST %": f"{a.kast_percent:.1f}%"
        })
    df_adv = pd.DataFrame(adv_rows)
    print(df_adv.to_string(index=False))

    # Table 3: ENTRY STATS
    print("\n🚪 3. ENTRY STATS")
    ent_rows = []
    for p, e in metrics.entry.items():
        ent_rows.append({
            "Player": f"⭐ {p}" if p == target_player else p,
            "Entry Kills": e.entry_kills,
            "Entry Deaths": e.entry_deaths,
            "Entry Diff": e.entry_difference,
            "Entry Success %": f"{e.entry_success_percent:.1f}%"
        })
    df_ent = pd.DataFrame(ent_rows)
    print(df_ent.to_string(index=False))

    # Table 4: TRADE STATS
    print("\n🔄 4. TRADE STATS")
    trd_rows = []
    for p, t in metrics.trade.items():
        trd_rows.append({
            "Player": f"⭐ {p}" if p == target_player else p,
            "Trade Kills": t.trade_kills,
            "Deaths Traded": t.deaths_traded,
            "Avg Trade Latency": f"{t.avg_trade_latency_ms:.0f} ms"
        })
    df_trd = pd.DataFrame(trd_rows)
    print(df_trd.to_string(index=False))

    # Table 5: CLUTCH STATS
    print("\n🏆 5. CLUTCH STATS")
    clu_rows = []
    for p, c in metrics.clutch.items():
        clu_rows.append({
            "Player": f"⭐ {p}" if p == target_player else p,
            "Clutch Wins": c.clutch_wins,
            "1v1": c.wins_1v1,
            "1v2": c.wins_1v2,
            "1v3": c.wins_1v3,
            "Clutch Success %": f"{c.clutch_success_percent:.1f}%"
        })
    df_clu = pd.DataFrame(clu_rows)
    print(df_clu.to_string(index=False))
    print("="*80 + "\n")
