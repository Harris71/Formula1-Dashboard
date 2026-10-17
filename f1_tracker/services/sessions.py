from pathlib import Path

import fastf1


SESSION_ALIASES = {
    "race": "R",
    "r": "R",
    "qualifying": "Q",
    "quali": "Q",
    "q": "Q",
}


def load_f1_session(year: int, grand_prix: str, session_type: str, cache_dir: Path):
    """Load a FastF1 session and enable project-local caching."""
    if not grand_prix.strip():
        raise ValueError("Grand Prix name cannot be empty.")

    session_code = SESSION_ALIASES.get(session_type.lower(), session_type)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))

    session = fastf1.get_session(year, grand_prix.strip(), session_code)
    session.load()
    return session
