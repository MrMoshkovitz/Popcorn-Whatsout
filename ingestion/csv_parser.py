"""Netflix CSV parser — transforms Netflix Viewing Activity CSV into ParsedEntry dicts."""

import csv
import logging
import re

from dateutil import parser as date_parser

SEASON_PATTERN = re.compile(
    r'^(Season|Part|עונה|חלק|Staffel)\s*(\d+)$',
    re.IGNORECASE
)


def _parse_date(date_str: str) -> str | None:
    """Parse a date string and return ISO format YYYY-MM-DD."""
    try:
        dt = date_parser.parse(date_str, dayfirst=True)
        return dt.strftime('%Y-%m-%d')
    except (ValueError, OverflowError):
        logging.warning(f"Could not parse date: {date_str}")
        return None


def parse_netflix_csv(file_path: str) -> list[dict]:
    """Parse a Netflix Viewing Activity CSV file into a list of ParsedEntry dicts.

    Each dict has keys: title, parsed_name, season_number, episode_name,
    watch_date, media_type_hint.
    """
    parsed = []
    skipped = 0

    try:
        with open(file_path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    title_raw = row.get("Title", "").strip()
                    date_raw = row.get("Date", "").strip()

                    if not title_raw or not date_raw:
                        logging.warning(f"Skipping malformed row: {row}")
                        skipped += 1
                        continue

                    watch_date = _parse_date(date_raw)
                    if watch_date is None:
                        skipped += 1
                        continue

                    segments = title_raw.split(": ")
                    parsed_name = segments[0]

                    season_number = None
                    season_index = None
                    episode_name = None

                    for i, segment in enumerate(segments[1:], start=1):
                        match = SEASON_PATTERN.match(segment.strip())
                        if match:
                            season_number = int(match.group(2))
                            season_index = i
                            break

                    if season_index is not None:
                        remaining = segments[season_index + 1:]
                        if remaining:
                            episode_name = ": ".join(remaining)

                    media_type_hint = "tv" if season_number is not None else "movie"

                    parsed.append({
                        "title": title_raw,
                        "parsed_name": parsed_name,
                        "season_number": season_number,
                        "episode_name": episode_name,
                        "watch_date": watch_date,
                        "media_type_hint": media_type_hint,
                    })

                except Exception as e:
                    logging.warning(f"Error processing row {row}: {e}")
                    skipped += 1

    except Exception as e:
        logging.error(f"Failed to open CSV file: {e}")
        return []

    logging.info(f"CSV parsing complete: {len(parsed)} parsed, {skipped} skipped")
    return parsed
