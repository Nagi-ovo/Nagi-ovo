import re
import json
import os
import time
from html import escape
from urllib.request import urlopen, Request

BLOG_BASE = "https://blog.nagi.fun"
BLOG_API = f"{BLOG_BASE}/api/posts"
# Cloudflare 403s the default "Python-urllib" User-Agent on any request that
# reaches the edge bot-check (i.e. every cache MISS), so a browser-like UA is
# required for the cache-busted fetch below.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
GITHUB_USER = "Nagi-ovo"
REPOS_WITH_RELEASES = ["gemini-voyager", "shiori-releases", "komorebi"]
PROFILE_ASSET_BASE = "https://github.com/Nagi-ovo/Nagi-ovo/blob/main/assets"
RELEASE_REPO_META = {
    "gemini-voyager": {
        "name": "Voyager",
        "logo": f"{PROFILE_ASSET_BASE}/release-gemini-voyager.png?raw=true",
        "include_prereleases": False,
    },
    "shiori-releases": {
        "name": "Shiori",
        "logo": f"{PROFILE_ASSET_BASE}/release-shiori.png?raw=true",
        "include_prereleases": True,
    },
    "komorebi": {
        "name": "Komorebi",
        "logo": "https://github.com/Nagi-ovo/komorebi/blob/main/icons/icon-32.png?raw=true",
        "include_prereleases": False,
    },
}
MAX_POSTS = 3
MAX_RELEASES = 3
BLOG_COVER_WIDTH = 180
GITHUB_PAGE_SIZE = 100
MAX_RELEASE_PAGES = 5


def github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{GITHUB_USER}-profile-readme",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers


def fetch_text(url, headers=None):
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode()


def fetch_json(url, headers=None):
    return json.loads(fetch_text(url, headers=headers))


def replace_chunk(content, marker, chunk):
    pattern = re.compile(
        r"<!-- {} starts -->.*<!-- {} ends -->".format(marker, marker),
        re.DOTALL,
    )
    replacement = "<!-- {} starts -->\n{}\n<!-- {} ends -->".format(marker, chunk, marker)
    return pattern.sub(replacement, content)


def absolute_blog_url(path):
    if not path:
        return None
    if path.startswith(("https://", "http://")):
        return path
    if path.startswith("/"):
        return f"{BLOG_BASE}{path}"
    return f"{BLOG_BASE}/{path}"


def blog_cover_url(post):
    for key in ("cover", "coverUrl", "image", "imageUrl"):
        cover = absolute_blog_url(post.get(key))
        if cover:
            return cover

    return None


def fetch_blog_posts():
    try:
        # /api/posts is served with max-age=3600 at Cloudflare's edge, so a
        # plain fetch can return a stale list right after a deploy (e.g. a post
        # just marked draft still showing). A per-run cache-bust param forces a
        # fresh read; the browser UA gets past CF's bot-check on the resulting
        # cache miss.
        posts = fetch_json(
            f"{BLOG_API}?t={int(time.time())}", headers=BROWSER_HEADERS
        )
        rows = []
        for post in posts[:MAX_POSTS]:
            title_cn = post["title"]
            title_en = post["titleEn"]
            date = post["date"][:10]
            url = f"{BLOG_BASE}/{post['slug']}"
            rows.append(format_blog_post(title_cn, title_en, url, date, blog_cover_url(post)))
        return "<table>\n{}\n</table>".format("\n".join(rows))
    except Exception as e:
        print(f"Error fetching blog posts: {e}")
        return ""


def format_blog_post(title_cn, title_en, url, date, cover):
    title_cn_html = escape(title_cn, quote=False)
    title_en_html = escape(title_en, quote=False)
    url_html = escape(url, quote=True)
    date_html = escape(date, quote=False)

    cover_cell = ""
    if cover:
        cover_html = escape(cover, quote=True)
        alt_html = escape(f"{title_cn} cover", quote=True)
        cover_cell = (
            f'<td width="{BLOG_COVER_WIDTH}" valign="top">'
            f'<a href="{url_html}">'
            f'<img src="{cover_html}" alt="{alt_html}" '
            f'width="{BLOG_COVER_WIDTH}" />'
            "</a></td>"
        )

    return (
        "<tr>"
        f"{cover_cell}"
        f'<td valign="top"><a href="{url_html}">{title_en_html}</a><br>'
        f"<sub>{title_cn_html} - {date_html}</sub></td>"
        "</tr>"
    )


def fetch_releases():
    releases = []
    for repo in REPOS_WITH_RELEASES:
        try:
            meta = RELEASE_REPO_META.get(repo, {})
            release = fetch_latest_release(
                repo,
                include_prereleases=meta.get("include_prereleases", False),
            )
            if not release:
                continue
            date = (release.get("published_at") or release.get("created_at") or "")[:10]
            releases.append({
                "repo": repo,
                "tag": release["tag_name"],
                "url": release["html_url"],
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


def fetch_latest_release(repo, include_prereleases=False):
    for page in range(1, MAX_RELEASE_PAGES + 1):
        data = fetch_json(
            f"https://api.github.com/repos/{GITHUB_USER}/{repo}/releases"
            f"?per_page={GITHUB_PAGE_SIZE}&page={page}",
            headers=github_headers(),
        )
        if not data:
            return None

        release = next(
            (
                item
                for item in data
                if not item.get("draft")
                and (include_prereleases or not item.get("prerelease"))
            ),
            None,
        )
        if release:
            return release

    return None


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
