import requests
from bs4 import BeautifulSoup
import urllib.parse
import sys
import json
import logging
import re
import os
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime

# === CONFIG ===
JELLYSEERR_URL = os.environ.get('JELLYSEERR_URL', 'http://192.168.0.29:5054')
JELLYSEERR_EMAIL = os.environ.get('JELLYSEERR_EMAIL')
JELLYSEERR_PASSWORD = os.environ.get('JELLYSEERR_PASSWORD')
IMDB_URL = os.environ.get('IMDB_URL', 'https://www.imdb.com/chart/moviemeter')
MOVIE_LIMIT = int(os.environ.get('MOVIE_LIMIT', 50))
RUN_INTERVAL_DAYS = int(os.environ.get('RUN_INTERVAL_DAYS', 7))
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'SIMPLE').upper()
IS_4K_REQUEST = os.environ.get('IS_4K_REQUEST', 'true').lower() == 'true'
LOG_FILE = "/logs/imdb_jellyseerr.log"

ACCESS_TOKEN = None  # Will hold JWT after login

# === Logging ===
logging_level = logging.DEBUG if DEBUG_MODE == 'VERBOSE' else logging.INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging_level)

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)


def authenticate_user():
    global ACCESS_TOKEN
    try:
        payload = {
            "email": JELLYSEERR_EMAIL,
            "password": JELLYSEERR_PASSWORD
        }
        res = requests.post(f"{JELLYSEERR_URL}/api/v1/auth/local", json=payload)
        if res.status_code == 200:
            ACCESS_TOKEN = res.json().get("accessToken")
            logger.info("✅ Successfully authenticated with JWT")
        else:
            logger.error(f"❌ Authentication failed: {res.status_code} - {res.text}")
    except Exception as e:
        logger.error(f"❌ Error during authentication: {e}")


def get_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Connection": "close"
    }


def normalize_title(title):
    if not title:
        return ""
    title = re.sub(r'[^\w\s]', '', title.lower())
    title = ' '.join(title.split())
    return title


def scrape_imdb_top_movies(limit=MOVIE_LIMIT):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(IMDB_URL, headers=headers, timeout=(5, 10))
        if response.status_code != 200:
            logger.error(f"Failed to fetch IMDb: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        json_ld = soup.find("script", type="application/ld+json")
        if json_ld:
            json_data = json.loads(json_ld.string)
            movies = []
            seen = set()
            if "itemListElement" in json_data:
                for item in json_data["itemListElement"]:
                    title = item.get("item", {}).get("name")
                    if title:
                        norm = normalize_title(title)
                        if norm and norm not in seen:
                            movies.append(title)
                            seen.add(norm)
                    if len(movies) >= limit:
                        break
                return movies

        movie_elements = soup.select("ul.ipc-metadata-list li.ipc-metadata-list-summary-item a h3")
        movie_elements = movie_elements[:limit]
        movies = []
        seen = set()
        for element in movie_elements:
            title = element.get_text().strip().split(". ")[-1]
            if title:
                norm = normalize_title(title)
                if norm and norm not in seen:
                    movies.append(title)
                    seen.add(norm)
            if len(movies) >= limit:
                break
        return movies
    except Exception as e:
        logger.error(f"IMDb scrape error: {e}")
        return []


def search_jellyseerr(movie_name, max_retries=3):
    encoded = urllib.parse.quote(movie_name, safe='')
    for attempt in range(1, max_retries + 1):
        try:
            with requests.Session() as session:
                retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
                session.mount('http://', HTTPAdapter(max_retries=retries))
                session.mount('https://', HTTPAdapter(max_retries=retries))
                res = session.get(
                    f"{JELLYSEERR_URL}/api/v1/search",
                    params={"query": encoded},
                    headers=get_headers(),
                    timeout=(5, 15)
                )
                if res.status_code == 200:
                    return res.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt} failed for '{movie_name}': {e}")
            time.sleep(2 ** attempt)
    return None


def get_movie_details(movie_name, json_data):
    if not json_data or "results" not in json_data:
        return None, None, None
    norm_query = normalize_title(movie_name)
    for result in json_data["results"]:
        if result.get("mediaType") == "movie":
            title = result.get("title", "")
            norm_title = normalize_title(title)
            imdb_id = result.get("mediaInfo", {}).get("imdbId") or result.get("imdbId")
            media_id = result.get("id")
            tmdb_id = result.get("tmdbId", media_id)
            if not title or not tmdb_id:
                continue
            if norm_query in norm_title:
                return imdb_id, media_id, tmdb_id
    return None, None, None


def make_request(tmdb_id, media_id):
    payload = {
        "mediaType": "movie",
        "tmdbId": tmdb_id,
        "mediaId": media_id,
        "is4k": IS_4K_REQUEST
    }
    try:
        with requests.Session() as session:
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
            session.mount('http://', HTTPAdapter(max_retries=retries))
            session.mount('https://', HTTPAdapter(max_retries=retries))
            res = session.post(
                f"{JELLYSEERR_URL}/api/v1/request",
                json=payload,
                headers=get_headers(),
                timeout=(5, 15)
            )
            if res.status_code == 201:
                logger.info(f"✅ Requested movie (tmdbId: {tmdb_id}, mediaId: {media_id}, is4k: {IS_4K_REQUEST})")
                return True, res.text
            else:
                logger.warning(f"⚠️ Request failed: {res.status_code} {res.text}")
                return False, res.text
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Request error: {e}")
        return False, str(e)


def main():
    logger.info(f"Jelly Request started with JWT (4K: {IS_4K_REQUEST})")
    authenticate_user()
    if not ACCESS_TOKEN:
        logger.error("❌ No access token retrieved. Exiting.")
        return

    while True:
        try:
            movies = scrape_imdb_top_movies()
            if not movies:
                logger.warning("No movies found.")
            else:
                logger.info(f"{len(movies)} movies to process")
                for i, movie in enumerate(movies, 1):
                    logger.info(f"[{i}/{len(movies)}] Searching: {movie}")
                    try:
                        data = search_jellyseerr(movie)
                        imdb_id, media_id, tmdb_id = get_movie_details(movie, data)
                        if tmdb_id:
                            make_request(tmdb_id, media_id)
                        else:
                            logger.info(f"Not found in Jellyseerr: {movie}")
                    except Exception as e:
                        logger.error(f"❌ Error with '{movie}': {e}")
        except Exception as e:
            logger.error(f"Main loop error: {e}")
        finally:
            logger.info(f"Sleeping {RUN_INTERVAL_DAYS} day(s)")
            time.sleep(RUN_INTERVAL_DAYS * 86400)


if __name__ == "__main__":
    main()
