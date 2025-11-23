#!/usr/bin/env python3
import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve

import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def run_command(cmd: list[str], timeout: int = 15) -> str | None:
    """Execute command and return stdout"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}\n{e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return None


def get_build_version(binary_path: str) -> str | None:
    """Get Build Version from nym-node binary"""
    logger.info(f"Getting version from: {binary_path}")
    output = run_command([binary_path, "--version"])
    if not output:
        return None
    
    for line in output.splitlines():
        if line.startswith("Build Version:"):
            version = line.split(":", 1)[1].strip()
            logger.info(f"Found version: {version}")
            return version
    
    logger.warning("Build Version not found in output")
    return None


def find_current_binary() -> str | None:
    """Find current nym-node installation"""
    binary = shutil.which("nym-node")
    if binary:
        logger.info(f"Found nym-node in PATH: {binary}")
        return binary
    
    fallback = Path.home() / ".nym" / "bin" / "nym-node"
    if fallback.exists() and os.access(fallback, os.X_OK):
        logger.info(f"Found nym-node at: {fallback}")
        return str(fallback)
    
    logger.error("nym-node binary not found")
    return None


def get_latest_release() -> tuple[str | None, str | None]:
    """Get latest release info from GitHub"""
    logger.info("Fetching latest release from GitHub...")
    try:
        response = requests.get(
            "https://api.github.com/repos/nymtech/nym/releases/latest",
            headers={"User-Agent": "nym-updater"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        tag = data["tag_name"]
        logger.info(f"Latest release: {tag}")
        
        for asset in data["assets"]:
            if asset["name"] == "nym-node":
                url = asset["browser_download_url"]
                logger.info(f"Download URL: {url}")
                return tag, url
        
        logger.error("'nym-node' asset not found in release")
        return None, None
    except Exception as e:
        logger.error(f"Failed to fetch release info: {e}")
        return None, None


def download_binary(url: str, dest: Path) -> bool:
    """Download binary to destination"""
    try:
        logger.info(f"Downloading to: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(url, dest)
        os.chmod(dest, 0o755)
        logger.info("Download complete")
        return True
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False


def update_binary(new_binary: Path, current_binary: str) -> bool:
    """Replace current binary with new one using sudo"""
    try:
        logger.info(f"Updating {current_binary} with {new_binary}")
        
        # Backup current binary
        backup = Path(current_binary).with_suffix('.backup')
        subprocess.run(['sudo', 'cp', current_binary, str(backup)], check=True)
        logger.info(f"Backup created: {backup}")
        
        # Replace with new binary
        subprocess.run(['sudo', 'cp', str(new_binary), current_binary], check=True)
        subprocess.run(['sudo', 'chmod', '755', current_binary], check=True)
        logger.info("Binary updated successfully")
        return True
    except Exception as e:
        logger.error(f"Update failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='nym-node updater')
    parser.add_argument('-y', '--yes', action='store_true', help='Automatically answer yes to all prompts')
    args = parser.parse_args()
    
    logger.info("=== nym-node Updater Started ===")
    
    # Find current binary
    current_binary = find_current_binary()
    if not current_binary:
        logger.error("Cannot proceed without current binary")
        sys.exit(1)
    
    # Get current version
    current_version = get_build_version(current_binary)
    if not current_version:
        logger.error("Cannot get current version")
        sys.exit(1)
    
    print(f"\n📦 Current Build Version: {current_version}")
    
    # Get latest release
    latest_tag, download_url = get_latest_release()
    if not latest_tag or not download_url:
        logger.error("Cannot get latest release info")
        sys.exit(1)
    
    print(f"🌐 Latest Release: {latest_tag}")
    
    # Download new binary
    tmp_dir = Path("/tmp/nym-update")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    
    new_binary = tmp_dir / "nym-node"
    if not download_binary(download_url, new_binary):
        sys.exit(1)
    
    # Get new version
    new_version = get_build_version(str(new_binary))
    if not new_version:
        logger.error("Cannot get new version")
        sys.exit(1)
    
    print(f"📥 Downloaded Build Version: {new_version}")
    
    # Compare versions
    if new_version > current_version:
        print(f"\n✅ Update available! ({new_version} > {current_version})")
        
        if args.yes:
            response = 'y'
            print("Auto-confirming update (-y flag)")
        else:
            response = input("\nDo you want to update? [y/N]: ").strip().lower()
        
        if response == 'y':
            if update_binary(new_binary, current_binary):
                print("\n✅ Update successful!")
                logger.info("Update completed successfully")
                
                # Ask to restart service
                if args.yes:
                    restart = 'y'
                    print("Auto-confirming service restart (-y flag)")
                else:
                    restart = input("\nRestart nym-node.service? [y/N]: ").strip().lower()
                
                if restart == 'y':
                    try:
                        subprocess.run(['sudo', 'systemctl', 'restart', 'nym-node.service'], check=True)
                        print("✅ Service restarted successfully")
                        logger.info("Service restarted")
                    except Exception as e:
                        print(f"❌ Failed to restart service: {e}")
                        logger.error(f"Service restart failed: {e}")
                else:
                    print("Service restart skipped")
            else:
                print("\n❌ Update failed!")
                sys.exit(1)
        else:
            print("Update cancelled")
            logger.info("Update cancelled by user")
    elif new_version == current_version:
        print("\nℹ️  Already up to date")
        logger.info("No update needed")
    else:
        print(f"\n⚠️  Downloaded version is older? ({new_version} < {current_version})")
        logger.warning("New version appears older than current")
    
    logger.info("=== nym-node Updater Finished ===")


if __name__ == "__main__":
    main()
