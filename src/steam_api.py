import requests

def check_profile_open(api_key: str, steam_id: str) -> dict:
    """Проверяет открыт ли профиль Steam (публичный, есть часы, есть недавние игры)"""
    U = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    O = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    R = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/"

    def j(url, params):
        try:
            r = requests.get(url, params=params, timeout=10)
            return r.json() if r.status_code == 200 else {}
        except Exception:
            return {}

    out = {'profile_public': False, 'has_games_with_playtime': False, 'has_recent_games': False, 'open': False, 'error': None}

    p = (j(U, {"key": api_key, "steamids": steam_id}).get("response", {}).get("players", []) or [{}])[0]
    out['profile_public'] = p.get('communityvisibilitystate') == 3 and p.get('profilestate') == 1

    g = j(O, {"key": api_key, "steamid": steam_id, "include_appinfo": 1}).get("response", {})
    gh = sum(x.get('playtime_forever', 0) for x in g.get('games', []))
    out['has_games_with_playtime'] = bool(g.get('game_count') and gh > 0)

    r = j(R, {"key": api_key, "steamid": steam_id}).get("response", {})
    out['has_recent_games'] = bool(r.get('total_count', 0) > 0)

    out['open'] = out['profile_public'] and out['has_games_with_playtime'] and out['has_recent_games']
    return out


def get_arma_games(api_key, steam_id, playtime: bool = False):
    """Возвращает игры ARMA/SQUAD/DayZ с ненулевым временем.
    playtime=True -> (name, hours), иначе -> name.
    """
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        'key': api_key,
        'steamid': steam_id,
        'include_appinfo': True
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return []

    data = response.json()
    games = data.get('response', {}).get('games', [])

    if playtime:
        result = []
        for game in games:
            name = game.get('name')
            pts = game.get('playtime_forever')
            if not name:
                continue
            upper = name.upper()
            if not ('ARMA' in upper or 'SQUAD' in upper or 'DAYZ' in upper):
                continue
            if isinstance(pts, int) and pts > 0:
                hours = round(pts / 60, 2)
                result.append((name, hours))
        return result

    result_names = []
    for game in games:
        name = game.get('name')
        pts = game.get('playtime_forever')
        if not name:
            continue
        upper = name.upper()
        if not ('ARMA' in upper or 'SQUAD' in upper or 'DAYZ' in upper):
            continue
        if isinstance(pts, int) and pts > 0:
            result_names.append(name)
    return result_names