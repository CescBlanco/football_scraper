# Football Scraper

Modular Python library for extracting football data from multiple public providers, including Understat, Sofascore, Fotmob, Transfermarkt, ESPN, Scoresway and 365Scores.

Provides structured access to match data, player statistics, teams, competitions, standings, transfers and live scores through provider-specific scraping modules.

---

# Features

- Multi-provider football data extraction
- Match, player, team and competition modules
- Live scores and match events
- Shared HTTP session handling
- Consistent provider structure
- Extensible provider architecture

---

# Installation

```bash
pip install football-scraper
```

To update to the latest version:

```bash
pip install --upgrade football-scraper
```

---

# Quick Start

```python
from football_scraper import FootballClient

client = FootballClient()

# Get Premier League matches (2024 season)
matches = client.understat.league.get_matches("EPL", 2024)

print(len(matches))
```

---

# Supported Providers

| Provider | Modules | Status |
|----------|----------|--------|
| Understat | Competitions, League, Team, Player, Match |✅ |
| Sofascore | Competitions, League, Team, Player, Manager, Match |✅ |
| Transfermarkt | Competitions, Team, Player|✅ |
| Fotmob | Competitions, League, Team, Player, Live Matches, Match |✅ |
| ESPN | Competitions, League, Team, Player, Match |✅ |
| Scoresway | Competitions, League, Team, Player, Pre-Match, Post-Match, Events |✅ |
| 365Scores | Competitions, League, Team, Player, Match |✅ |

---

# Example Usage

## Understat

```python
client.understat.competitions.get_competition('La liga')

client.understat.league.extract_teams(league_name='La liga', season='2025')

client.understat.team.extract_players('Barcelona', '2025')

client.understat.player.extract_stats_season('Barcelona', 'Lamine Yamal','2025'  )

client.understat.match.extract_match_stats("https://understat.com/match/29479")
```

## Sofascore

```python
client.sofascore.competition.extract_all_countries()

client.sofascore.league.extract_standings_total_home_away(id_league_selected, id_season_selected, type= 'total')

client.sofascore.team.extract_recent_form('2817')

client.sofascore.player.extract_attributes_summary('1402912')    

client.sofascore.match.extract_heatmap_player("14083113", '1402912')

client.sofascore.manager.extract_career_history_manager('793676')
```

## Transfermarkt

```python
client.transfermarkt.competition.get_by_name('LaLiga - Spain (ES1)')

client.transfermarkt.team.extract_experience_team( "https://www.transfermarkt.com/fc-barcelona/erfahrung/verein/131/wettbewerbAuswahl/ES1/plus/1")

client.transfermarkt.player.extract_penalty_goals("https://www.transfermarkt.com/mike-maignan/elfmeterstatistik/spieler/182906/saison_id//wettbewerb_id//plus/1", is_goalkeeper=True)
```

## Fotmob

```python
client.fotmob.competition.find_leagues("Premier League")

client.fotmob.league.extract_transfer("LaLiga - Spain", "2025/2026",ccode3="ESP")

client.fotmob.team.extract_historical_table_position('https://www.fotmob.com/teams/8634/overview/barcelona', ccode3='ESP')

client.fotmob.player.extract_heatmap_season_stats("https://www.fotmob.com/players/696679/raphinha")

client.fotmob.matches_live_today.extract_matches_live_full()

client.fotmob.match.extract_match_momentum("https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426")

```

## ESPN

```python
client.espn.competition.list_competitions_available()

client.espn.league.extract_transfers('Portuguese Primeira Liga', year='2025')

client.espn.team.extract_results('FC Porto', "Portuguese Primeira Liga", '2025')

client.espn.player.extract_last5_matches_current_year("Portuguese Primeira Liga", 'FC Porto' , "2025", "Alberto Costa")

client.espn.match.extract_match_timeline('https://www.espn.com/soccer/match/_/gameId/750528/alverca-fc-porto')
```

## Scoresway

```python
client.scoresway.competition.get_league_by_country_and_name('Spain', 'Primera División')

client.scoresway.league.extract_team_kits('Spain', 'Primera División', 'Barcelona', season= '2025/2026')

client.scoresway.team.extract_team_fixtures("Spain", "Primera División", "Barcelona",  season= '2025/2026')

client.scoresway.pre_match.extract_match_details("https://www.scoresway.com/en_GB/soccer/primera-divisi%C3%B3n-2025-2026/80zg2v1cuqcfhphn56u4qpyqc/match/view/3xq4alyjtlltd6j11gckoxvkk/match-preview")

client.scoresway.post_match.extract_referees("https://www.scoresway.com/en_GB/soccer/primera-divisi%C3%B3n-2025-2026/80zg2v1cuqcfhphn56u4qpyqc/match/view/3rpa9gg887sphjnou8h1uv6s4/match-summary")

client.scoresway.events_match.expand_events(events ,"pass")
```

## 365scores

```python
client.scores365.competition.get_by_name( 'LaLiga')

client.scores365.league.extract_actual_team_of_week('LaLiga')

client.scores365.team.extract_next_matches("https://www.365scores.com/football/team/fc-barcelona-132")

client.scores365.player.extract_trophies('https://www.365scores.com/football/player/raphinha-39789')

client.scores365.match.extract_match_stats("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

```

---

# Requirements

- Python 3.10+

---

# Disclaimer

Football Scraper is an unofficial Python library and is not affiliated with any of the supported providers.

All data and trademarks belong to their respective owners.

Users are responsible for complying with the terms of service of each provider.

---

# Roadmap

Planned improvements:

- Expand provider coverage with additional football data sources
- Extend module functionality across existing providers
- Full documentation per provider and module
- Enhanced reliability (error handling, retries, request stability)
- Optional async support for selected providers


# License

MIT License — see LICENSE file for details.