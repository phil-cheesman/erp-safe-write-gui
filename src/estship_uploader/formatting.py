"""Output formatting for CLI and GUI display."""

MAX_VALUE_LENGTH = 500


def truncate_value(val, max_len: int = MAX_VALUE_LENGTH) -> str:
    """Truncate long values, appending total char count."""
    if val is None:
        return ""
    s = str(val)
    if len(s) > max_len:
        return s[:max_len] + f"... ({len(s)} chars total)"
    return s


def format_step_result(result) -> str:
    """Format a StepResult for display: [PASS]/[FAIL]/[WARN] + message + details."""
    tag_map = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARNING": "[WARN]"}
    tag = tag_map.get(result.status, f"[{result.status}]")
    lines = [f"{tag} {result.message}"]
    for detail in result.details:
        lines.append(f"  {detail}")
    return "\n".join(lines)


def format_upload_summary(total: int, earliest: str, latest: str) -> str:
    """Format the post-upload summary line."""
    return (
        f"Upload complete: {total} rows updated\n"
        f"  Earliest: {earliest}  Latest: {latest}"
    )
