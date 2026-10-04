from typing import Any, Dict

def calculate_health_scores(repo_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Compute multidimensional health scores from repository statistics."""

    # 1. Activity Score (0 - 100)
    days = repo_stats.get("days_since_last_commit", 999)
    if days <= 7:
        activity_base = 100
    elif days <= 14:
        activity_base = 88
    elif days <= 30:
        activity_base = 75
    elif days <= 60:
        activity_base = 60
    elif days <= 120:
        activity_base = 45
    elif days <= 240:
        activity_base = 25
    else:
        activity_base = 10

    # Adjust by commit density in the sample
    sample_commits = repo_stats.get("recent_commits_count", 0)
    if sample_commits >= 25:
        activity_score = min(100, activity_base)
    elif sample_commits >= 10:
        activity_score = min(100, int(activity_base * 0.95))
    else:
        activity_score = max(5, int(activity_base * 0.8))

    # 2. Community & Documentation Score (0 - 100)
    community_score = 0
    if repo_stats.get("has_readme"):
        community_score += 35
    if repo_stats.get("has_license"):
        community_score += 30
    if repo_stats.get("has_contributing"):
        community_score += 20
    if repo_stats.get("has_code_of_conduct"):
        community_score += 15

    # 3. Issue Health Score (0 - 100)
    open_issues = repo_stats.get("open_issues_count", 0)
    closed_issues = repo_stats.get("closed_issues_count", 0)
    total_issues = open_issues + closed_issues

    if total_issues == 0:
        issue_score = 80
    else:
        closed_ratio = closed_issues / total_issues
        if closed_ratio >= 0.75:
            issue_score = 95
        elif closed_ratio >= 0.50:
            issue_score = 80
        elif closed_ratio >= 0.25:
            issue_score = 65
        else:
            issue_score = 40
        if open_issues > 1000 and closed_ratio < 0.6:
            issue_score = max(20, issue_score - 15)

    # 4. Pull Request & Collaboration Score (0 - 100)
    prs = repo_stats.get("sample_pull_requests", {})
    total_prs = prs.get("total_sampled", 0)
    merged_prs = prs.get("merged", 0)

    if total_prs == 0:
        pr_score = 75
    else:
        merge_ratio = merged_prs / total_prs
        pr_score = int(30 + (merge_ratio * 70))
        pr_score = min(100, max(20, pr_score))

    # 5. Overall Weighted Score
    # Weights: Activity 30%, Community 25%, Issues 25%, PRs 20%
    overall_score = round(
        (activity_score * 0.30) +
        (community_score * 0.25) +
        (issue_score * 0.25) +
        (pr_score * 0.20)
    )
    overall_score = min(100, max(0, overall_score))

    # Determine Grade and Status
    if overall_score >= 90:
        grade = "A+"
        status = "Thriving"
        color = "#10b981"
    elif overall_score >= 80:
        grade = "A"
        status = "Healthy"
        color = "#22c55e"
    elif overall_score >= 70:
        grade = "B"
        status = "Good"
        color = "#3b82f6"
    elif overall_score >= 55:
        grade = "C"
        status = "Needs Attention"
        color = "#f59e0b"
    elif overall_score >= 40:
        grade = "D"
        status = "At Risk"
        color = "#f97316"
    else:
        grade = "F"
        status = "Inactive or Stale"
        color = "#ef4444"

    return {
        "overall_score": overall_score,
        "grade": grade,
        "status": status,
        "status_color": color,
        "categories": {
            "activity": {
                "score": activity_score,
                "label": "Maintenance & Activity",
                "days_since_last_commit": days,
                "weight": 30,
            },
            "community": {
                "score": community_score,
                "label": "Community & Governance",
                "has_readme": repo_stats.get("has_readme"),
                "has_license": repo_stats.get("has_license"),
                "has_contributing": repo_stats.get("has_contributing"),
                "has_code_of_conduct": repo_stats.get("has_code_of_conduct"),
                "weight": 25,
            },
            "issues": {
                "score": issue_score,
                "label": "Issue Resolution",
                "open_issues": open_issues,
                "closed_issues": closed_issues,
                "weight": 25,
            },
            "pull_requests": {
                "score": pr_score,
                "label": "PR & Contribution Velocity",
                "merged_ratio": round(merged_prs / max(1, total_prs), 2),
                "weight": 20,
            }
        }
    }
