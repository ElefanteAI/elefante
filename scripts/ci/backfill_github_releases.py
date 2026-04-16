import argparse
import subprocess
import sys
import re
from pathlib import Path


def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return False, result.stderr
    return True, result.stdout


def main():
    print("Checking GitHub CLI authentication...")
    success, out = run_cmd("gh auth status")
    if not success:
        print("ERROR: GitHub CLI not authenticated. Please run 'gh auth login' first.")
        sys.exit(1)

    print("Getting list of existing GitHub releases...")
    success, releases_out = run_cmd("gh release list --limit 100")
    if not success:
        print(f"ERROR fetching releases: {releases_out}")
        sys.exit(1)

    # Parse releases
    # gh release list output format: Title \t Type \t Tag \t Date
    tags = []
    for line in releases_out.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) >= 3:
            tags.append(parts[2])

    print(f"Found {len(tags)} releases. Backfilling changelogs...")

    for tag in tags:
        if not tag.startswith('v'):
            continue
        
        version = tag[1:]  # strip 'v'
        print(f"\nProcessing {tag}...")

        # 1. Render markdown for this version using our new CI script
        render_cmd = f"python scripts/ci/render_release_notes.py {version}"
        success, rendered_out = run_cmd(render_cmd)
        
        if not success:
            print(f"  [SKIP] Could not render release notes for {version}: {rendered_out.strip()}")
            continue

        # Create a temp file for the notes
        notes_file = Path(f"/tmp/release_notes_{version}.md")
        notes_file.write_text(rendered_out)

        # 2. Update the release on GitHub
        print(f"  Updating GitHub Release {tag}...")
        update_cmd = f"gh release edit {tag} --notes-file {notes_file}"
        success, update_out = run_cmd(update_cmd)

        if success:
            print(f"  [SUCCESS] {tag} updated.")
        else:
            print(f"  [ERROR] Failed to update {tag}: {update_out.strip()}")
        
        # Cleanup
        notes_file.unlink(missing_ok=True)

    print("\nBackfill complete! Check your GitHub releases page.")

if __name__ == "__main__":
    main()
