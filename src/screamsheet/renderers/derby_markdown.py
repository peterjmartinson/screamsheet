"""Renderer for formatting MLB Home Run Derby summary into a clean Markdown block."""
from typing import Any, Dict


def format_derby_markdown(data: Dict[str, Any]) -> str:
    """
    Format the Home Run Derby summary data dictionary into a tight Markdown block.
    
    Args:
        data: Dictionary returned by MLBDataProvider.get_home_run_derby_summary
        
    Returns:
        Clean, formatted Markdown string
    """
    if not data:
        return "No Home Run Derby data available."
        
    bracket = data.get("bracket", {})
    statcast = data.get("statcast", {})
    
    lines = []
    lines.append("# 🏆 MLB Home Run Derby Summary")
    lines.append("")
    
    champion = bracket.get("champion")
    runner_up = bracket.get("runner_up")
    
    if champion and runner_up:
        lines.append(f"**Champion:** {champion.get('player')} ({champion.get('hits')} HR in Finals)  ")
        lines.append(f"**Runner-Up:** {runner_up.get('player')} ({runner_up.get('hits')} HR in Finals)  ")
    else:
        lines.append("**Champion:** TBD  ")
        lines.append("**Runner-Up:** TBD  ")
        
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### ⚾ Round-by-Round Bracket")
    lines.append("")
    lines.append("| Round | Player | HR | Status |")
    lines.append("| :--- | :--- | :---: | :--- |")
    
    rounds = bracket.get("rounds", [])
    for rnd in rounds:
        round_name = rnd.get("round_name", "")
        matchups = rnd.get("matchups", [])
        for m_idx, m in enumerate(matchups):
            top = m.get("top_seed", {})
            bot = m.get("bottom_seed", {})
            winner = m.get("winner")
            
            top_p = top.get("player", "TBD")
            top_h = top.get("hits", 0)
            bot_p = bot.get("player", "TBD")
            bot_h = bot.get("hits", 0)
            
            top_status = "Advanced" if top_p == winner else "Eliminated"
            bot_status = "Advanced" if bot_p == winner else "Eliminated"
            
            if round_name == "Finals":
                top_status = "Champion" if top_p == winner else "Runner-Up"
                bot_status = "Champion" if bot_p == winner else "Runner-Up"
                
            r_label = f"**{round_name}**" if m_idx == 0 else ""
            lines.append(f"| {r_label} | {top_p} | {top_h} | {top_status} |")
            lines.append(f"| | {bot_p} | {bot_h} | {bot_status} |")
            
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 🚀 Statcast Highlights")
    
    longest = statcast.get("longest_hr", {})
    hardest = statcast.get("hardest_hit", {})
    
    longest_dist = longest.get("distance", 0)
    longest_player = longest.get("player", "N/A")
    hardest_vel = hardest.get("exit_velocity", 0.0)
    hardest_player = hardest.get("player", "N/A")
    
    lines.append(f"* **Longest Home Run:** {longest_dist} ft — *{longest_player}*")
    lines.append(f"* **Hardest Hit Ball:** {hardest_vel} mph — *{hardest_player}*")
    lines.append("")
    
    return "\n".join(lines)
