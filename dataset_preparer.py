import zipfile
from pathlib import Path
from config import Config


class DatasetPreparer:
    def __init__(self, config: Config):
        self.config = config
        self.data_root = config.root_dir / config.data_root
        self.excel_path = config.root_dir / config.excel_path
        self.zip_path = config.root_dir / config.timeline_zip_path

    def prepare(self) -> dict:
        result = {
            "excel_exists": False,
            "zip_exists": False,
            "data_root_exists": False,
            "cves_dir_exists": False,
            "advisories_dir_exists": False,
            "prepared": False,
            "errors": [],
        }

        # Check Excel
        if self.excel_path.exists():
            result["excel_exists"] = True
        else:
            result["errors"].append(f"Excel file not found: {self.excel_path}")

        # Check zip
        if self.zip_path.exists():
            result["zip_exists"] = True
        else:
            result["errors"].append(f"Zip file not found: {self.zip_path}")

        # Check data root
        if self.data_root.exists():
            result["data_root_exists"] = True
        else:
            # Try to extract zip
            if result["zip_exists"]:
                try:
                    self._extract_zip()
                    result["data_root_exists"] = True
                except Exception as e:
                    result["errors"].append(f"Failed to extract zip: {e}")

        # Check subdirectories
        if result["data_root_exists"]:
            cves_dir = self.data_root / "cves"
            advisories_dir = self.data_root / "security_advisories"

            result["cves_dir_exists"] = cves_dir.exists()
            result["advisories_dir_exists"] = advisories_dir.exists()

            if not result["cves_dir_exists"]:
                result["errors"].append(f"cves directory not found: {cves_dir}")
            if not result["advisories_dir_exists"]:
                result["errors"].append(f"security_advisories directory not found: {advisories_dir}")

        result["prepared"] = (
            result["excel_exists"]
            and result["data_root_exists"]
            and result["cves_dir_exists"]
            and result["advisories_dir_exists"]
        )

        return result

    def _extract_zip(self):
        self.data_root.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            # Skip __MACOSX entries
            members = [m for m in zf.namelist() if not m.startswith("__MACOSX")]

            # Detect if zip has a single root directory containing cves/ or security_advisories/
            top_level = set()
            for m in members:
                parts = m.split("/")
                if parts and parts[0]:
                    top_level.add(parts[0])

            # Check if cves/ or security_advisories/ are already at top level
            has_cves_at_top = "cves" in top_level
            has_advisories_at_top = "security_advisories" in top_level

            if has_cves_at_top or has_advisories_at_top:
                # Already at correct level, extract directly
                extract_root = self.data_root
                prefix = ""
            elif len(top_level) == 1:
                # Single root directory - strip it
                root_name = top_level.pop()
                prefix = root_name + "/"
                extract_root = self.data_root
            else:
                # Unknown structure, extract directly
                extract_root = self.data_root
                prefix = ""

            for member in members:
                if not member.startswith(prefix):
                    continue
                rel_path = member[len(prefix):]
                if not rel_path:
                    continue
                target = extract_root / rel_path
                if member.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())

    def generate_report(self, result: dict) -> str:
        lines = [
            "# Pre-flight Report",
            "",
            "## Data Status",
            "",
            f"| Item | Status |",
            f"|------|--------|",
            f"| Excel file | {'✅' if result['excel_exists'] else '❌'} |",
            f"| Timeline zip | {'✅' if result['zip_exists'] else '❌'} |",
            f"| Data root | {'✅' if result['data_root_exists'] else '❌'} |",
            f"| CVEs directory | {'✅' if result['cves_dir_exists'] else '❌'} |",
            f"| Advisories directory | {'✅' if result['advisories_dir_exists'] else '❌'} |",
            f"| **Prepared** | {'✅' if result['prepared'] else '❌'} |",
            "",
        ]

        if result["errors"]:
            lines.extend([
                "## Errors",
                "",
            ])
            for err in result["errors"]:
                lines.append(f"- {err}")
            lines.append("")

        return "\n".join(lines)
