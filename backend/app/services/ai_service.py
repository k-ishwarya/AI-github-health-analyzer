import os
import json
from typing import Any, Dict, List

def generate_heuristic_insights(repo_stats: Dict[str, Any], scores: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback generator that constructs contextual health insights from metrics."""
    overall = scores["overall_score"]
    name = repo_stats.get("full_name", "Repository")
    categories = scores["categories"]

    strengths: List[str] = []
    risks: List[str] = []
    recommendations: List[Dict[str, str]] = []

    # Activity
    days = repo_stats.get("days_since_last_commit", 999)
    if days <= 7:
        strengths.append(f"Highly active development cadence with commits made in the last {days} days.")
    elif days <= 30:
        strengths.append("Steady commit activity over the past month.")
    else:
        risks.append(f"Last commit was {days} days ago, indicating low recent maintenance velocity.")
        recommendations.append({
            "priority": "High" if days > 90 else "Medium",
            "title": "Resume Regular Maintenance",
            "description": f"The repository hasn't had commits in {days} days. Review dependencies, security advisories, and triage pull requests."
        })

    # Community files
    if repo_stats.get("has_readme"):
        strengths.append("Comprehensive README file present for onboarding new contributors.")
    else:
        risks.append("Missing README.md makes it difficult for developers to understand the project.")
        recommendations.append({
            "priority": "High",
            "title": "Add a descriptive README.md",
            "description": "Include project overview, installation steps, configuration guides, and usage examples."
        })

    if repo_stats.get("has_license"):
        license_name = repo_stats.get("license_name") or "open source license"
        strengths.append(f"Explicit licensing ({license_name}) grants legal clarity to users and contributors.")
    else:
        risks.append("No open-source license detected, which discourages enterprise and open source adoption.")
        recommendations.append({
            "priority": "High",
            "title": "Add an Open Source License",
            "description": "Choose a permissive or copyleft license (e.g., MIT, Apache-2.0, GPLv3) to protect authors and enable collaboration."
        })

    if not repo_stats.get("has_contributing"):
        recommendations.append({
            "priority": "Medium",
            "title": "Add CONTRIBUTING.md Guidelines",
            "description": "Provide a contribution guide detailing branch naming, pull request expectations, and local dev setup."
        })

    if not repo_stats.get("has_code_of_conduct"):
        recommendations.append({
            "priority": "Low",
            "title": "Establish a Code of Conduct",
            "description": "Adopt standard community standards (e.g. Contributor Covenant) to foster a welcoming environment."
        })

    # Issues
    open_issues = repo_stats.get("open_issues_count", 0)
    closed_issues = repo_stats.get("closed_issues_count", 0)
    if open_issues > 200:
        recommendations.append({
            "priority": "Medium",
            "title": "Automate Issue Triage",
            "description": f"With {open_issues} open issues, implement GitHub Actions or stale-issue bots to categorize and prioritize bug reports."
        })

    # Summary
    if overall >= 80:
        summary = f"{name} demonstrates strong open-source health with solid community standards and active maintenance."
    elif overall >= 60:
        summary = f"{name} is moderately healthy but would benefit from governance documentation and more frequent triage cycles."
    else:
        summary = f"{name} exhibits signs of stagnation or missing governance files. Immediate attention is recommended."

    return {
        "summary": summary,
        "strengths": strengths if strengths else ["Repository is publicly accessible."],
        "risks": risks if risks else ["No critical governance or maintenance risks detected."],
        "recommendations": recommendations if recommendations else [
            {
                "priority": "Low",
                "title": "Maintain Continuous Integration",
                "description": "Ensure CI/CD workflows run on all active pull requests to maintain code quality."
            }
        ],
        "ai_powered": False
    }


async def generate_ai_insights(repo_stats: Dict[str, Any], scores: Dict[str, Any]) -> Dict[str, Any]:
    """Generate AI insights using Gemini API if key is available, else heuristic fallback."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return generate_heuristic_insights(repo_stats, scores)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""
        Analyze the open-source health of the following GitHub repository:
        Name: {repo_stats.get('full_name')}
        Description: {repo_stats.get('description')}
        Primary Language: {repo_stats.get('language')}
        Stars: {repo_stats.get('stars')} | Forks: {repo_stats.get('forks')}
        Days since last commit: {repo_stats.get('days_since_last_commit')}
        Open issues: {repo_stats.get('open_issues_count')} | Closed issues: {repo_stats.get('closed_issues_count')}
        Has README: {repo_stats.get('has_readme')}
        Has License: {repo_stats.get('has_license')} ({repo_stats.get('license_name')})
        Has Contributing Guide: {repo_stats.get('has_contributing')}
        Has Code of Conduct: {repo_stats.get('has_code_of_conduct')}
        Overall Health Score: {scores.get('overall_score')}/100 (Grade: {scores.get('grade')})

        Return ONLY a valid JSON object matching this exact structure:
        {{
            "summary": "2-3 sentences assessing current state and trajectory",
            "strengths": ["string", "string"],
            "risks": ["string", "string"],
            "recommendations": [
                {{
                    "priority": "High" | "Medium" | "Low",
                    "title": "short title",
                    "description": "actionable instruction"
                }}
            ]
        }}
        """

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        text = response.text.strip()
        # Strip potential markdown formatting ```json ... ```
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]

        parsed = json.loads(text.strip())
        parsed["ai_powered"] = True
        return parsed
    except Exception:
        # Fallback cleanly on error or missing rate limit
        return generate_heuristic_insights(repo_stats, scores)
