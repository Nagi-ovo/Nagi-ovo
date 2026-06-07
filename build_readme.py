import re
import json
import os
from urllib.request import urlopen, Request
from datetime import datetime

BLOG_API = "https://blog.nagi.fun/api/posts"
GITHUB_USER = "Nagi-ovo"
REPOS_WITH_RELEASES = ["gemini-voyager", "shiori-releases"]
PROFILE_ASSET_BASE = "https://github.com/Nagi-ovo/Nagi-ovo/blob/main/assets"
RELEASE_REPO_META = {
    "gemini-voyager": {
        "name": "Gemini Voyager",
        "logo": f"{PROFILE_ASSET_BASE}/release-gemini-voyager.png?raw=true",
    },
    "shiori-releases": {
        "name": "Shiori",
        "logo": f"{PROFILE_ASSET_BASE}/release-shiori.png?raw=true",
    },
}
MAX_POSTS = 3
MAX_RELEASES = 3


def fetch_json(url, headers=None):
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def replace_chunk(content, marker, chunk):
    pattern = re.compile(
        r"<!-- {} starts -->.*<!-- {} ends -->".format(marker, marker),
        re.DOTALL,
    )
    replacement = "<!-- {} starts -->\n{}\n<!-- {} ends -->".format(marker, chunk, marker)
    return pattern.sub(replacement, content)


def fetch_blog_posts():
    try:
        posts = fetch_json(BLOG_API)
        results = []
        for post in posts[:MAX_POSTS]:
            title_cn = post["title"]
            title_en = post["titleEn"]
            date = post["date"][:10]
            url = f"https://blog.nagi.fun/{post['slug']}"
            results.append(f"• [{title_cn} / {title_en}]({url}) - {date}")
        return "<br>".join(results)
    except Exception as e:
        print(f"Error fetching blog posts: {e}")
        return ""


def fetch_releases():
    headers = {"Accept": "application/vnd.github+json"}

    releases = []
    for repo in REPOS_WITH_RELEASES:
        try:
            data = fetch_json(
                f"https://api.github.com/repos/{GITHUB_USER}/{repo}/releases",
                headers=headers,
            )
            for release in data[:2]:
                tag = release["tag_name"]
                url = release["html_url"]
                date = release["published_at"][:10]
                releases.append({
                    "repo": repo,
                    "tag": tag,
                    "url": url,
                    "date": date,
                })
        except Exception as e:
            print(f"Error fetching releases for {repo}: {e}")

    releases.sort(key=lambda r: r["date"], reverse=True)
    md = "<br>".join(
        format_release(r)
        for r in releases[:MAX_RELEASES]
    )
    return md


def format_release(release):
    meta = RELEASE_REPO_META.get(release["repo"], {})
    name = meta.get("name", release["repo"])
    logo = meta.get("logo")

    if logo:
        icon = (
            f'<img src="{logo}" alt="{name} logo" width="18" height="18" '
            'align="absmiddle" />&nbsp;'
        )
    else:
        icon = "• "

    return f"{icon}[{name} {release['tag']}]({release['url']}) - {release['date']}"


if __name__ == "__main__":
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    with open(readme_path, "r") as f:
        content = f.read()

    blog_md = fetch_blog_posts()
    if blog_md:
        content = replace_chunk(content, "blog", blog_md)

    releases_md = fetch_releases()
    if releases_md:
        content = replace_chunk(content, "releases", releases_md)

    with open(readme_path, "w") as f:
        f.write(content)

    print("README updated successfully.")
