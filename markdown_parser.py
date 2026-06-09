import re
from pathlib import Path


def extract_bullet_value(markdown_text: str, key: str) -> str:
    """Extract value from markdown bullet point like '- key: value'."""
    pattern = rf"^[ \t]*-[ \t]*{re.escape(key)}[ \t]*:[ \t]*(.*)$"
    match = re.search(pattern, markdown_text, re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def extract_section(markdown_text: str, section_name: str) -> str:
    """Extract content under a markdown section header."""
    pattern = rf"##\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, markdown_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


# Empty value patterns to normalize to "none" (不含 insufficient_evidence，它是有效语义)
EMPTY_VALUES = {"N/A", "(不适用)", "(not applicable)", "", "none"}

# Valid enum values for specific fields
VALID_CATEGORY = {"A", "B", "C", "INSUFFICIENT_EVIDENCE"}
VALID_DIFFICULTY = {"easy", "medium", "hard", "unknown", "insufficient_evidence"}
VALID_YES_NO = {"yes", "no", "uncertain", "insufficient_evidence"}
VALID_CATEGORY_NAME = {
    "传统类型漏洞", "AI功能实现+传统方式", "AI场景新漏洞模式",
    "insufficient_evidence", "none",
}
VALID_AI_NATIVE_SUBTYPE = {
    "none", "direct_prompt_injection", "indirect_prompt_injection",
    "rag_poisoning", "tool_output_poisoning", "memory_poisoning",
    "delegation_hijack", "semantic_policy_bypass", "unknown",
    "insufficient_evidence",
}


def normalize_value(value: str, field_name: str = "") -> str:
    """Normalize extracted values for consistent statistics."""
    if not value:
        return "none"

    # Strip and lowercase for comparison
    stripped = value.strip()
    lower = stripped.lower()

    # Check empty patterns (不含 insufficient_evidence)
    if lower in {v.lower() for v in EMPTY_VALUES}:
        return "none"

    # Field-specific normalization
    if field_name == "category":
        upper = stripped.upper()
        return upper if upper in VALID_CATEGORY else stripped
    elif field_name == "difficulty":
        return lower if lower in VALID_DIFFICULTY else stripped
    elif field_name in ("requires_ai_function", "cross_agent", "manual_review_needed"):
        return lower if lower in VALID_YES_NO else stripped
    elif field_name == "category_name":
        return stripped if stripped in VALID_CATEGORY_NAME else stripped
    elif field_name == "ai_native_subtype":
        return lower if lower in VALID_AI_NATIVE_SUBTYPE else stripped

    return stripped


def parse_metadata(metadata_path: Path) -> dict:
    """Parse metadata.md file and extract basic info fields."""
    if not metadata_path.exists():
        return {}

    text = metadata_path.read_text(encoding="utf-8")

    # Extract fields using bold key format: **Key**: value
    def extract_bold_value(text: str, key: str) -> str:
        pattern = rf"\*\*{re.escape(key)}\*\*\s*:\s*(.+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    result = {}
    field_mapping = {
        "Project": "project",
        "GitHub URL": "github_url",
        "Source": "source",
        "CVE ID": "cve_id",
        "Advisory ID": "adv_id",
        "Published At": "publish_at",
        "CWE": "cwe",
    }

    for display_name, field_name in field_mapping.items():
        value = extract_bold_value(text, display_name)
        if value and value != "N/A":
            result[field_name] = value

    return result


def parse_step1(text: str) -> dict:
    """Parse Step 1: Version Verification output."""
    return {
        "intro_time_verdict": normalize_value(extract_bullet_value(text, "intro_time_verdict"), "intro_time_verdict"),
        "vuln_exists_at_intro_version": normalize_value(extract_bullet_value(text, "vuln_exists_at_intro_version"), "vuln_exists_at_intro_version"),
        "manual_review_needed": normalize_value(extract_bullet_value(text, "manual_review_needed"), "manual_review_needed"),
    }


def parse_step2(text: str) -> dict:
    """Parse Step 2: Module Classification output."""
    return {
        "classification_type": extract_bullet_value(text, "classification_type"),
        "primary_module": extract_bullet_value(text, "primary_module"),
        "secondary_modules": extract_bullet_value(text, "secondary_modules"),
        "confidence": normalize_value(extract_bullet_value(text, "confidence"), "confidence"),
        "architecture_type": extract_bullet_value(text, "architecture_type"),
        "architecture_confidence": normalize_value(extract_bullet_value(text, "architecture_confidence"), "architecture_confidence"),
    }


def parse_step3(text: str) -> dict:
    """Parse Step 3: Vulnerability Pattern Classification output."""
    return {
        "category": normalize_value(extract_bullet_value(text, "category"), "category"),
        "category_name": normalize_value(extract_bullet_value(text, "category_name"), "category_name"),
        "module_from_step2_primary": extract_bullet_value(text, "module_from_step2_primary"),
        "module_from_step2_secondary": extract_bullet_value(text, "module_from_step2_secondary"),
        "module_from_step2_classification_type": extract_bullet_value(text, "module_from_step2_classification_type"),
        "input_type": extract_bullet_value(text, "input_type"),
        "input_subtype": extract_bullet_value(text, "input_subtype"),
        "mechanism_type": extract_bullet_value(text, "mechanism_type"),
        "mechanism_subtype": extract_bullet_value(text, "mechanism_subtype"),
        "requires_ai_function": normalize_value(extract_bullet_value(text, "requires_ai_function"), "requires_ai_function"),
        "ai_native_subtype": normalize_value(extract_bullet_value(text, "ai_native_subtype"), "ai_native_subtype"),
        "cross_agent": normalize_value(extract_bullet_value(text, "cross_agent"), "cross_agent"),
    }


def parse_step4(text: str) -> dict:
    """Parse Step 4: Exploit Condition Summary output."""
    return {
        "difficulty": normalize_value(extract_bullet_value(text, "difficulty"), "difficulty"),
    }


def parse_all_steps(step1_text: str, step2_text: str, step3_text: str, step4_text: str) -> dict:
    """Parse all step outputs and return combined fields."""
    result = {}
    result.update(parse_step1(step1_text))
    result.update(parse_step2(step2_text))
    result.update(parse_step3(step3_text))
    result.update(parse_step4(step4_text))
    return result


def parse_task_output(task_dir: Path) -> dict:
    """Parse all step files from a task output directory."""
    result = {}

    step_files = {
        "01_version_verification.md": parse_step1,
        "02_module_classification.md": parse_step2,
        "03_vulnerability_pattern_classification.md": parse_step3,
        "04_exploit_condition_summary.md": parse_step4,
    }

    for filename, parser in step_files.items():
        filepath = task_dir / filename
        if filepath.exists():
            text = filepath.read_text(encoding="utf-8")
            result.update(parser(text))

    return result
