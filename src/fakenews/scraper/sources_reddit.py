"""Subreddits suivis (US-02 scraper, cf. doc/userstories_scraper.md).

Liste modifiable sans toucher au code de collecte (src/fakenews/scraper/reddit.py).
"""

SUBREDDITS = [
    # -- Actualité générale --
    "worldnews",
    "news",
    # -- Finance --
    "wallstreetbets",
    "stocks",
    "investing",
]

NB_POSTS_PAR_SUBREDDIT = 100
