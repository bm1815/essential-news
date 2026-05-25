from jinja2 import Environment, FileSystemLoader
import feedparser
import anthropic
import json
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# --- CONFIG ---
FEEDS = [
    "https://feeds.reuters.com/reuters/worldNews",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.dw.com/rdf/rss-en-world",
]

MAX_STORIES = 8
import os
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# --- STEP 1: FETCH ARTICLES ---
def fetch_articles():
    articles = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:15]:  # take top 15 from each feed
            articles.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", "")
            })
    return articles

# --- STEP 2: CLASSIFY WITH CLAUDE ---
def is_essential(article):
    prompt = f"""You are a strict news filter. Your job is to decide if a news story is 'essential' — meaning it significantly affects the state of the world or fundamentally impacts people's lives at scale.

Essential topics: geopolitics, wars, conflicts, major elections, significant economic shifts, climate events, public health crises, major policy changes, natural disasters.

NOT essential: celebrity news, entertainment, sports, lifestyle, human interest stories, minor local events.

Article title: {article['title']}
Article summary: {article['summary']}

Reply with JSON only, no other text:
{{"essential": true or false, "reason": "one sentence explanation"}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )
    
    raw = response.content[0].text
    
    
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        return result.get("essential", False), result.get("reason", "")
    except:
        print(f"   JSON parse failed")
        return False, ""

# --- STEP 3: SUMMARIZE WITH CLAUDE ---
def summarize(article):
    prompt = f"""Summarize this news story in exactly 2 clear sentences. Focus on what happened and why it matters globally. No fluff.

Title: {article['title']}
Summary: {article['summary']}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text.strip()

# --- MAIN ---
def main():
    print("Fetching articles...")
    articles = fetch_articles()
    print(f"Found {len(articles)} articles. Classifying...")

    essential_articles = []
    for article in articles:
        essential, reason = is_essential(article)
        if essential:
            print(f"✓ {article['title']}")
            summary = summarize(article)
            essential_articles.append({
                "title": article["title"],
                "summary": summary,
                "reason": reason,
                "link": article["link"]
            })
        else:
            print(f"✗ {article['title']}")

        if len(essential_articles) >= MAX_STORIES:
            break

    print(f"\nSelected {len(essential_articles)} essential stories.")
    return essential_articles

if __name__ == "__main__":
    stories = main()

    # clean up stray "# Summary" text
    for s in stories:
        s["summary"] = s["summary"].replace("# Summary", "").strip()

    # render HTML
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("template.html")
    html = template.render(
        stories=stories,
        date=datetime.now().strftime("%B %d, %Y"),
        count=len(stories)
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("\n✅ index.html generated successfully.")