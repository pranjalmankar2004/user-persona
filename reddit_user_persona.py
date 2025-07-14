import sys
import re
import requests
import json
import os
from collections import defaultdict



USER_AGENT = "Mozilla/5.0 (compatible; RedditUserPersonaBot/0.1)"


def extract_username(profile_url):
    match = re.search(r"reddit.com/user/([\w-]+)/?", profile_url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid Reddit user profile URL.")


def fetch_user_content(username, limit=100):
    headers = {"User-Agent": USER_AGENT}
    posts_url = f"https://www.reddit.com/user/{username}/submitted.json?limit={limit}"
    comments_url = f"https://www.reddit.com/user/{username}/comments.json?limit={limit}"
    posts_resp = requests.get(posts_url, headers=headers)
    comments_resp = requests.get(comments_url, headers=headers)
    if posts_resp.status_code == 404 or comments_resp.status_code == 404:
        print(f"User '{username}' does not exist or is not accessible. Exiting.")
        sys.exit(1)
    posts = posts_resp.json()
    comments = comments_resp.json()
    post_items = posts.get("data", {}).get("children", [])
    comment_items = comments.get("data", {}).get("children", [])
    return post_items, comment_items


def extract_text_and_citations(post_items, comment_items):
    texts = []
    citations = []
    for post in post_items:
        data = post["data"]
        title = data.get("title", "")
        selftext = data.get("selftext", "")
        subreddit = data.get("subreddit", "")
        url = f'https://www.reddit.com{data.get("permalink", "")}'
        text = f"{title}\n{selftext}".strip()
        if text:
            texts.append(text)
            citations.append((text, subreddit, url))
    for comment in comment_items:
        data = comment["data"]
        body = data.get("body", "")
        subreddit = data.get("subreddit", "")
        url = f'https://www.reddit.com{data.get("permalink", "")}'
        if body:
            texts.append(body)
            citations.append((body, subreddit, url))
    return texts, citations


def analyze_persona(texts, citations):
    persona = defaultdict(lambda: "Not clear from data.")
    evidence = defaultdict(list)
    long_posts = 0
    short_posts = 0
    expressive = 0
    sarcastic = 0
    empathetic = 0
    for i, (text, subreddit, url) in enumerate(citations):
        lower = text.lower()
        word_count = len(text.split())
        if word_count > 100:
            long_posts += 1
        else:
            short_posts += 1
        if any(x in lower for x in ["i feel", "i'm sorry", "that must be hard", "hope you're ok"]):
            empathetic += 1
            persona["Personality Traits"] = "Empathetic"
            evidence["Personality Traits"].append(f'"{text[:60]}..." – {url}')
        if any(x in lower for x in ["oh yeah, because", "sure, that'll work", "as if", "🙄"]):
            sarcastic += 1
            persona["Writing Style and Tone"] = "Sarcastic"
            evidence["Writing Style and Tone"].append(f'"{text[:60]}..." – {url}')
        if any(x in lower for x in ["i love", "i enjoy", "my favorite", "i like"]):
            expressive += 1
            persona["Personality Traits"] = "Expressive"
            evidence["Personality Traits"].append(f'"{text[:60]}..." – {url}')
        if "anime" in lower or subreddit.lower() == "anime":
            persona["Top Interests"] = persona.get("Top Interests", []) + ["Anime"]
            evidence["Top Interests"].append(f'"{text[:60]}..." – {url}')
        if "game" in lower or subreddit.lower() == "gaming":
            persona["Top Interests"] = persona.get("Top Interests", []) + ["Gaming"]
            evidence["Top Interests"].append(f'"{text[:60]}..." – {url}')
        if "work" in lower or "job" in lower:
            persona["Occupation"] = "Mentions work/job"
            evidence["Occupation"].append(f'"{text[:60]}..." – {url}')
        if "i believe" in lower or "i think" in lower:
            persona["Core Values and Beliefs"] = text
            evidence["Core Values and Beliefs"].append(f'"{text[:60]}..." – {url}')
        if "struggle" in lower or "hard" in lower or "challenge" in lower:
            persona["Pain Points and Challenges"] = text
            evidence["Pain Points and Challenges"].append(f'"{text[:60]}..." – {url}')
        if any(x in lower for x in [":)", ":(", "lol", "haha"]):
            persona["Writing Style and Tone"] = "Informal, uses emoticons or internet slang"
            evidence["Writing Style and Tone"].append(f'"{text[:60]}..." – {url}')
    # Deduplicate interests
    if "Top Interests" in persona:
        persona["Top Interests"] = list(set(persona["Top Interests"]))
    # Reddit Usage Behavior
    if long_posts > 0 and long_posts >= short_posts:
        persona["Reddit Usage Behavior"] = "Prefers long-form posts"
    elif short_posts > 0:
        persona["Reddit Usage Behavior"] = "Prefers short comments/posts"
    # Personality Traits fallback
    if not persona["Personality Traits"] or persona["Personality Traits"] == "Not clear from data.":
        if expressive > 0:
            persona["Personality Traits"] = "Expressive"
        elif empathetic > 0:
            persona["Personality Traits"] = "Empathetic"
        elif sarcastic > 0:
            persona["Personality Traits"] = "Sarcastic"
    return persona, evidence


def build_persona_output(username, persona, evidence):
    output = []
    output.append("---\nUSER PERSONA\n")
    output.append(f"**Name**: {username.capitalize()} (generated)\n")
    # Age range note
    age_note = "Not explicitly mentioned, possibly 20–35 based on context and subreddits."
    output.append(f"**Age Range**: {age_note}\n")
    output.append(f"**Occupation**: {persona.get('Occupation', 'Not clear from data.')}\n")
    if persona.get('Top Interests', []):
        output.append(f"**Top Interests**:\n- " + "\n- ".join(persona.get('Top Interests', [])) + "\n")
    else:
        output.append(f"**Top Interests**: Not clear from data.\n")
    output.append(f"**Goals and Aspirations**: {persona.get('Goals and Aspirations', 'Not clear from data.')}\n")
    output.append(f"**Core Values and Beliefs**: {persona.get('Core Values and Beliefs', 'Not clear from data.')}\n")
    output.append(f"**Pain Points and Challenges**: {persona.get('Pain Points and Challenges', 'Not clear from data.')}\n")
    output.append(f"**Writing Style and Tone**: {persona.get('Writing Style and Tone', 'Not clear from data.')}\n")
    output.append(f"**Personality Traits**: {persona.get('Personality Traits', 'Not clear from data.')}\n")
    output.append(f"**Reddit Usage Behavior**: {persona.get('Reddit Usage Behavior', 'Not clear from data.')}\n")
    output.append("\n---\n\n**EVIDENCE / CITATIONS:**\n")
    for trait, cites in evidence.items():
        seen = set()
        count = 0
        for cite in cites:
            if cite in seen:
                continue
            seen.add(cite)
            # Format: - **Trait**: "snippet..." – [Reddit Link]
            snippet, url = cite.split(' – ')
            output.append(f"- **{trait}**: {snippet} – [{url}]({url})")
            count += 1
            if count >= 3:
                break
    return "\n".join(output)


def llm_persona_analysis(texts, username, api_key):
    import openai
    openai.api_key = api_key
    prompt = f"""
You are a user profiling expert. Given the following Reddit posts and comments from user '{username}', generate a qualitative user persona including: Name, Age Range, Occupation, Top Interests, Goals and Aspirations, Core Values and Beliefs, Pain Points and Challenges, Writing Style and Tone, Personality Traits, Reddit Usage Behavior. For each trait, cite the post/comment (or a snippet) you used. If not clear, say 'Not clear from data.'

Reddit posts/comments:
{texts[:3000]}
"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800
    )
    return response.choices[0].message['content']


def hf_llm_persona_analysis(texts, username, api_key, model="mistralai/Mixtral-8x7B-Instruct-v0.1"):
    import requests
    prompt = f"""
You are a user profiling expert. Given the following Reddit posts and comments from user '{username}', generate a qualitative user persona including: Name, Age Range, Occupation, Top Interests, Goals and Aspirations, Core Values and Beliefs, Pain Points and Challenges, Writing Style and Tone, Personality Traits, Reddit Usage Behavior. For each trait, cite the post/comment (or a snippet) you used. If not clear, say 'Not clear from data.'

Reddit posts/comments:
{texts[:3000]}
"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 800}
    }
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{model}",
        headers=headers,
        data=json.dumps(payload)
    )
    if response.status_code != 200:
        return f"[HF API Error {response.status_code}]: {response.text}"
    result = response.json()
    if isinstance(result, dict) and 'error' in result:
        return f"[HF API Error]: {result['error']}"
    if isinstance(result, list) and 'generated_text' in result[0]:
        return result[0]['generated_text']
    return str(result)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('profile_url', help='Reddit user profile URL')
    parser.add_argument('--use-llm', action='store_true', help='Use OpenAI LLM for persona analysis')
    parser.add_argument('--openai-api-key', default=None, help='OpenAI API key (or set OPENAI_API_KEY env var)')
    parser.add_argument('--use-hf-llm', action='store_true', help='Use Hugging Face LLM for persona analysis')
    parser.add_argument('--hf-api-key', default=None, help='Hugging Face API key (or set HF_API_KEY env var)')
    args = parser.parse_args()
    profile_url = args.profile_url
    username = extract_username(profile_url)
    print(f"Fetching data for user: {username}")
    post_items, comment_items = fetch_user_content(username)
    if not post_items and not comment_items:
        print(f"No data found for user '{username}'. Exiting.")
        sys.exit(1)
    texts, citations = extract_text_and_citations(post_items, comment_items)
    persona, evidence = analyze_persona(texts, citations)
    persona_output = build_persona_output(username, persona, evidence)
    # LLM analysis if requested
    if args.use_llm:
        api_key = (
            args.openai_api_key
            or os.environ.get('OPENAI_API_KEY')
            or "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"
        )
        if not api_key:
            print('OpenAI API key required for LLM analysis. Set --openai-api-key or OPENAI_API_KEY env var.')
            sys.exit(1)
        print('Running LLM persona analysis (OpenAI)...')
        llm_output = llm_persona_analysis("\n".join(texts), username, api_key)
        persona_output = persona_output + "\n\n---\n\n**LLM Persona Analysis (OpenAI):**\n" + llm_output
    if args.use_hf_llm:
        hf_api_key = args.hf_api_key or os.environ.get('HF_API_KEY')
        if not hf_api_key:
            print('Hugging Face API key required for HF LLM analysis. Set --hf-api-key or HF_API_KEY env var.')
            sys.exit(1)
        print('Running LLM persona analysis (Hugging Face)...')
        hf_llm_output = hf_llm_persona_analysis("\n".join(texts), username, hf_api_key)
        persona_output = persona_output + "\n\n---\n\n**LLM Persona Analysis (Hugging Face):**\n" + hf_llm_output
    output_file = f"{username}_persona.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(persona_output)
    print(f"User persona written to {output_file}")

if __name__ == "__main__":
    main()
