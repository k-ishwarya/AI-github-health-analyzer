import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import httpx
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

GITHUB_API_BASE = "https://api.github.com"
_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
CACHE_TTL = 300  # 5 minutes cache

def parse_github_url(url_or_slug: str) -> Tuple[str, Optional[str]]:
    """Extract (owner, repo) or (owner, None) if user profile provided."""
    cleaned = url_or_slug.strip().split("?")[0].split("#")[0].rstrip("/")
    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail="Repository URL or slug cannot be empty."
        )

    # 1. Handle SSH format: git@github.com:owner/repo(.git)
    ssh_match = re.search(r"git@github\.com:([^/]+)/([^/]+)", cleaned)
    if ssh_match:
        owner = ssh_match.group(1)
        repo = ssh_match.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo

    # 2. Handle web URLs: (https?://)?(www\.)?github\.com/owner(/repo)?
    web_match = re.search(r"(?:https?://)?(?:www\.)?github\.com/([^/]+)(?:/([^/]+))?", cleaned)
    if web_match:
        owner = web_match.group(1)
        repo = web_match.group(2)
        if repo:
            if repo.endswith(".git"):
                repo = repo[:-4]
            return owner, repo
        return owner, None

    # 3. Handle slug formats: owner/repo or owner
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) >= 2:
        repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
        return parts[0], repo
    elif len(parts) == 1:
        return parts[0], None

    raise HTTPException(
        status_code=400,
        detail="Invalid GitHub URL or repository slug. Example: https://github.com/owner/repo or owner/repo"
    )

def _get_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-GitHub-Health-Analyzer",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def _extract_github_embedded_json(html: str) -> dict:
    """Extract GitHub's embedded react JSON payload from an HTML page (script[4])."""
    scripts = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)
    for s in scripts:
        try:
            obj = json.loads(s)
            payload = obj.get("payload", {})
            if "codeViewRepoRoute" in payload or "commitsRefRoute" in payload or "sidebarAbout" in payload:
                return payload
        except Exception:
            pass
    return {}

async def _fetch_web_fallback(owner: str, repo: str) -> Dict[str, Any]:
    """
    Fallback when GitHub API rate limit is exceeded.
    Reads the embedded JSON GitHub ships in its HTML pages for accurate real data.
    """
    import json as _json
    wb_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    base_url = f"https://github.com/{owner}/{repo}"

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        main_resp = await client.get(base_url, headers=wb_headers)
        if main_resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Repository '{owner}/{repo}' not found on GitHub.")
        if main_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"GitHub is not accessible right now. Try adding a GITHUB_TOKEN to .env")
        main_html = main_resp.text

    # ---- Parse embedded JSON from main repo page ----
    main_payload = _extract_github_embedded_json(main_html)
    route = main_payload.get("codeViewRepoRoute", {})
    sidebar = main_payload.get("sidebarAbout", {})

    # Real stars, forks, watchers from sidebarAbout
    stars = sidebar.get("stargazerCount", 0)
    forks = sidebar.get("forksCount", 0)
    watchers = sidebar.get("watcherCount", 0)

    # Default branch from route
    ref_info = route.get("refInfo", {})
    default_branch = ref_info.get("name", "main")

    # File list to detect governance files
    file_items = route.get("tree", {}).get("items", [])
    file_names_upper = {f.get("name", "").upper() for f in file_items}

    has_readme = any(n.startswith("README") for n in file_names_upper)
    has_license = any(n.startswith("LICENSE") or n == "COPYING" for n in file_names_upper)
    has_contributing = any(n.startswith("CONTRIBUTING") for n in file_names_upper)
    has_code_of_conduct = any(n.startswith("CODE_OF_CONDUCT") for n in file_names_upper)

    # Language from sidebar languages section (if present)
    language = "Not specified"
    lang_match = re.search(r'itemprop=["\']programmingLanguage["\']>([^<]+)<', main_html)
    if lang_match:
        language = lang_match.group(1).strip()

    # Description via og:description meta tag
    desc_match = re.search(r'<meta\s+(?:name|property)=["\'](?:og:description|description)["\']\s+content=["\']([^"\']*)["\']', main_html)
    description = html.unescape(desc_match.group(1).strip()) if desc_match else "Public GitHub repository."
    if "contribute to" in description.lower() and "development by creating an account" in description.lower():
        description = "Public GitHub repository."

    # ---- Fetch commits history (Atom feed first for 100% reliability, then HTML fallback) ----
    days_since_last_commit = 999
    latest_commit_date = None
    recent_commits_count = 0

    # 1. Try public Atom feed (fast, resilient, avoids web scraping blocks)
    try:
        atom_url = f"https://github.com/{owner}/{repo}/commits/{default_branch}.atom"
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            atom_resp = await client.get(atom_url)
            if atom_resp.status_code == 200:
                root = ET.fromstring(atom_resp.text)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                entries = root.findall("atom:entry", ns)
                recent_commits_count = len(entries)
                if entries:
                    updated_elem = entries[0].find("atom:updated", ns)
                    if updated_elem is not None and updated_elem.text:
                        latest_commit_date = updated_elem.text
                        clean_date = latest_commit_date.replace("Z", "+00:00")
                        commit_dt = datetime.fromisoformat(clean_date)
                        if commit_dt.tzinfo is None:
                            commit_dt = commit_dt.replace(tzinfo=timezone.utc)
                        days_since_last_commit = max(0, (datetime.now(timezone.utc) - commit_dt).days)
    except Exception:
        pass

    # 2. If Atom feed was unavailable, fallback to HTML embedded route parser
    if recent_commits_count == 0:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                commits_resp = await client.get(f"{base_url}/commits/{default_branch}", headers=wb_headers)
                if commits_resp.status_code == 200:
                    commits_payload = _extract_github_embedded_json(commits_resp.text)
                    commit_groups = commits_payload.get("commitsRefRoute", {}).get("commitGroups", [])

                    all_commits = []
                    for group in commit_groups:
                        all_commits.extend(group.get("commits", []))

                    recent_commits_count = len(all_commits)

                    if all_commits:
                        first_date_str = all_commits[0].get("committedDate")
                        if first_date_str:
                            latest_commit_date = first_date_str
                            try:
                                clean_date = first_date_str.replace("Z", "+00:00")
                                commit_dt = datetime.fromisoformat(clean_date)
                                if commit_dt.tzinfo is None:
                                    commit_dt = commit_dt.replace(tzinfo=timezone.utc)
                                days_since_last_commit = max(0, (datetime.now(timezone.utc) - commit_dt).days)
                            except Exception:
                                pass
        except Exception:
            pass

    # ---- Open issues count from HTML ----
    open_issues_count = 0
    issue_match = re.search(r'"issuesCount"\s*:\s*(\d+)', main_html)
    if issue_match:
        open_issues_count = int(issue_match.group(1))
    else:
        issue_match2 = re.search(r'(\d+)\s+[Oo]pen\s+[Ii]ssues', main_html)
        if issue_match2:
            try:
                open_issues_count = int(issue_match2.group(1))
            except Exception:
                pass

    return {
        "owner": owner,
        "repo": repo,
        "full_name": f"{owner}/{repo}",
        "description": description,
        "html_url": base_url,
        "stars": stars,
        "forks": forks,
        "watchers": watchers,
        "language": language,
        "default_branch": default_branch,
        "open_issues_count": open_issues_count,
        "closed_issues_count": 0,
        "has_readme": has_readme,
        "has_license": has_license,
        "license_name": None,
        "has_contributing": has_contributing,
        "has_code_of_conduct": has_code_of_conduct,
        "recent_commits_count": recent_commits_count,
        "latest_commit_date": latest_commit_date,
        "days_since_last_commit": days_since_last_commit,
        "sample_pull_requests": {
            "total_sampled": 0,
            "open": 0,
            "closed": 0,
            "merged": 0,
        },
        "rate_limited": True
    }

async def fetch_repository_data(owner: str, repo: str) -> Dict[str, Any]:
    """Fetch repository metadata, with automatic caching and web fallback on rate limits."""
    cache_key = f"{owner.lower()}/{repo.lower()}"
    now = time.time()
    if cache_key in _CACHE:
        cached_time, cached_data = _CACHE[cache_key]
        if now - cached_time < CACHE_TTL:
            return cached_data

    headers = _get_headers()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            repo_resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", headers=headers)
            
            # If rate limited (403 or 429), smoothly fallback to HTML parser!
            if repo_resp.status_code in (403, 429):
                data = await _fetch_web_fallback(owner, repo)
                _CACHE[cache_key] = (now, data)
                return data

            if repo_resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Repository '{owner}/{repo}' not found on GitHub.")
            if repo_resp.status_code != 200:
                data = await _fetch_web_fallback(owner, repo)
                _CACHE[cache_key] = (now, data)
                return data

            repo_data = repo_resp.json()

            # Community profile
            community_data = {}
            try:
                comm_resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/community/profile", headers=headers)
                if comm_resp.status_code == 200:
                    community_data = comm_resp.json().get("files", {})
            except Exception:
                pass

            # Recent commits
            commits_data = []
            try:
                commits_resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits?per_page=30", headers=headers)
                if commits_resp.status_code == 200:
                    commits_data = commits_resp.json()
            except Exception:
                pass

            # Pull requests
            pulls_data = []
            try:
                pulls_resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls?state=all&per_page=30", headers=headers)
                if pulls_resp.status_code == 200:
                    pulls_data = pulls_resp.json()
            except Exception:
                pass

            # Closed issues
            closed_issues_count = 0
            try:
                search_resp = await client.get(
                    f"{GITHUB_API_BASE}/search/issues?q=repo:{owner}/{repo}+type:issue+state:closed",
                    headers=headers
                )
                if search_resp.status_code == 200:
                    closed_issues_count = search_resp.json().get("total_count", 0)
            except Exception:
                pass

        # Parse flags
        has_readme = bool(community_data.get("readme"))
        if not has_readme:
            try:
                readme_check = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme", headers=headers)
                has_readme = (readme_check.status_code == 200)
            except Exception:
                pass

        has_license = bool(repo_data.get("license")) or bool(community_data.get("license"))
        has_contributing = bool(community_data.get("contributing"))
        has_code_of_conduct = bool(community_data.get("code_of_conduct"))

        latest_commit_date = None
        days_since_last_commit = 999
        if commits_data and isinstance(commits_data, list):
            try:
                raw_date = commits_data[0]["commit"]["committer"]["date"]
                latest_commit_date = raw_date
                commit_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                days_since_last_commit = max(0, (datetime.now(timezone.utc) - commit_dt).days)
            except Exception:
                pass

        open_prs = sum(1 for p in pulls_data if p.get("state") == "open")
        closed_prs = sum(1 for p in pulls_data if p.get("state") == "closed")
        merged_prs = sum(1 for p in pulls_data if p.get("merged_at") is not None)

        result = {
            "owner": owner,
            "repo": repo,
            "full_name": repo_data.get("full_name", f"{owner}/{repo}"),
            "description": repo_data.get("description") or "No description provided.",
            "html_url": repo_data.get("html_url"),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "watchers": repo_data.get("watchers_count", 0),
            "language": repo_data.get("language") or "Not specified",
            "default_branch": repo_data.get("default_branch", "main"),
            "open_issues_count": repo_data.get("open_issues_count", 0),
            "closed_issues_count": closed_issues_count,
            "has_readme": has_readme,
            "has_license": has_license,
            "license_name": repo_data.get("license", {}).get("name") if repo_data.get("license") else None,
            "has_contributing": has_contributing,
            "has_code_of_conduct": has_code_of_conduct,
            "recent_commits_count": len(commits_data),
            "latest_commit_date": latest_commit_date,
            "days_since_last_commit": days_since_last_commit,
            "sample_pull_requests": {
                "total_sampled": len(pulls_data),
                "open": open_prs,
                "closed": closed_prs,
                "merged": merged_prs,
            },
            "rate_limited": False
        }

        _CACHE[cache_key] = (now, result)
        return result

    except HTTPException:
        raise
    except Exception:
        # Fallback to web scrape on any network/API block
        data = await _fetch_web_fallback(owner, repo)
        _CACHE[cache_key] = (now, data)
        return data

async def fetch_user_repositories(username: str) -> list:
    """Fetch public repositories for a user profile, with web fallback if API rate-limited."""
    headers = _get_headers()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GITHUB_API_BASE}/users/{username}/repos?sort=updated&per_page=12", headers=headers)
            if resp.status_code == 200:
                return [
                    {
                        "name": r.get("name"),
                        "full_name": r.get("full_name"),
                        "html_url": r.get("html_url"),
                        "description": r.get("description") or "No description",
                        "stars": r.get("stargazers_count", 0),
                        "language": r.get("language") or "Other"
                    }
                    for r in resp.json()
                ]
    except Exception:
        pass

    # Fallback to public profile page
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                f"https://github.com/{username}?tab=repositories",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            if resp.status_code == 200:
                raw_names = set(re.findall(rf'href=["\']/{re.escape(username)}/([^"\'/?#]+)["\']', resp.text))
                ignored = {"followers", "following", "stars", "projects", "packages", "sponsors", "feed"}
                valid = [r for r in raw_names if r.lower() not in ignored and not r.startswith(".")]
                if valid:
                    return [
                        {"name": name, "full_name": f"{username}/{name}", "html_url": f"https://github.com/{username}/{name}"}
                        for name in sorted(valid)[:12]
                    ]
    except Exception:
        pass
    return []
