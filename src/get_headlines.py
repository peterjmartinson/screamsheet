import requests
import xml.etree.ElementTree as ET
# from datetime import datetime
# import re
# import os

def fetch_and_process_headlines():
    """
    Fetches, parses, and formats headlines from an RSS feed, saving them to a file.
    This is the clean Python equivalent of the provided Bash pipeline.
    """
    URL = "https://www.lemonde.fr/rss/une.xml"
    MAX_HEADLINES = 12
    # OUTPUT_FILE = "latest_news.txt"  # Matching the final output file name in the bash script

    print(f"Fetching headlines from {URL}...")

    # 1. Fetch the RSS XML content
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching RSS feed: {e}")
        return

    # 2. Parse the XML content
    # The 'ET.fromstring()' function safely parses the XML, avoiding regex issues.
    try:
        # The RSS structure typically has a root, then a 'channel', then 'item' tags.
        root = ET.fromstring(response.content)
        channel = root.find('channel')
    except ET.ParseError as e:
        print(f"Error parsing XML content: {e}")
        return

    # 3. Extract and filter headlines
    headlines = []
    # Find all 'item' elements within the 'channel'
    for item in channel.findall('item'):
        title_element = item.find('title')
        if title_element is not None:
            # .text handles CDATA and returns the clean text content, replacing grep/sed regex logic
            headline = title_element.text
            headlines.append(headline.strip())

    # 4. Filter, Limit, and Format the output (equivalent to sed 1d, head, nl)
    # The first 'item' in some feeds can be a summary; usually, only the actual news items are wanted.
    # In this structure, we just skip the main channel title and take the top N item titles.

    # 4a. Skip the main feed title (equivalent to sed '1d' if we were parsing all titles)
    # With ElementTree, we only extract titles from <item> blocks, which are the articles.

    # 4b. Limit the output (equivalent to head -n "$MAX_HEADLINES")
    headlines_to_write = []
    for i, line in enumerate(headlines[:MAX_HEADLINES], 1):
        headlines_to_write.append(f"{i}. {line}")

    return headlines_to_write


if __name__ == '__main__':
    print(fetch_and_process_headlines())
