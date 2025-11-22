"""
Nym Node Installer - Automated installation and configuration
(Refactored)
"""

import os
import sys
import json
import time
import argparse
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
import shutil


# ========== Enums ==========
class NodeMode(Enum):
    """Node operation modes"""
    MIXNODE = "mixnode"
    EXIT_GATEWAY = "exit-gateway"


class Color(Enum):
    """ANSI color codes"""
    GREEN_BRIGHT = "\033[92m"
    GREEN_LIGHT = "\033[38;5;42m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"
    BG_DARK_RED = "\033[48;5;124m"
    BG_YELLOW = "\033[103m"
    BG_GREEN = "\033[102m"
    HIGHLIGHT_BG = "\033[48;5;22m"
    HIGHLIGHT_FG = "\033[38;5;154m"


# ========== Data Classes ==========
@dataclass
class NodeConfig:
    """Node configuration data"""
    node_id: str = ""
    public_ip: str = ""
    binary_path: str = "/usr/local/bin/nym-node"
    node_mode: NodeMode = NodeMode.MIXNODE
    wireguard_enabled: bool = False
    cosmos_mnemonic: str = ""
    rpc_endpoint: str = "https://nym-rpc.polkachu.com/"

    @property
    def config_dir(self) -> Path:
        """Get node configuration directory"""
        return Path.home() / ".nym" / "nym-nodes" / self.node_id

    @property
    def data_dir(self) -> Path:
        """Get node data directory"""
        return self.config_dir / "data"


@dataclass
class BondingInfo:
    """Node bonding information"""
    identity_key: str = ""
    host: str = ""


@dataclass
class InstallationSteps:
    """Installation steps configuration"""
    system_update: bool = True
    dependencies: bool = True
    binary_download: bool = True
    mode_selection: bool = True
    firewall: bool = True
    node_init: bool = True
    service_setup: bool = True

    def get_active_steps(self) -> List[Tuple[str, bool]]:
        """Get list of active installation steps"""
        return [
            ("System Update", self.system_update),
            ("Dependency Installation", self.dependencies),
            ("Binary Download", self.binary_download),
            ("Mode Selection", self.mode_selection),
            ("Firewall Configuration", self.firewall),
            ("Node Initialization", self.node_init),
            ("Service Setup", self.service_setup),
        ]

    def count_active(self) -> int:
        """Count number of active steps"""
        return sum(1 for _, enabled in self.get_active_steps() if enabled)


# ========== Utility Classes ==========
class ProgressIndicator:
    """Animated progress indicator for long operations"""

    def __init__(self, message: str, spinner: str = '|/-\\'):
        self.message = message
        self.spinner = spinner
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self) -> None:
        """Start progress animation"""
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def stop(self, success_msg: Optional[str] = None) -> None:
        """Stop progress animation"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("\r" + " " * 100 + "\r", end="", flush=True)
        if success_msg:
            Logger.success(success_msg)

    def _animate(self) -> None:
        """Animation loop"""
        idx = 0
        while self.running:
            char = self.spinner[idx % len(self.spinner)]
            print(f"\r{Color.GREEN_LIGHT.value}{char} {self.message}...{Color.END.value}", 
                  end="", flush=True)
            time.sleep(0.1)
            idx += 1


class Logger:
    """Enhanced logging with colors and formatting"""

    @staticmethod
    def success(message: str) -> None:
        print(f"{Color.GREEN_BRIGHT.value}{Color.BOLD.value}✓ {Color.END.value}"
              f"{Color.GREEN_LIGHT.value}{message}{Color.END.value}")

    @staticmethod
    def error(message: str) -> None:
        print(f"{Color.RED.value}{Color.BOLD.value}✗ ERROR:{Color.END.value} "
              f"{Color.RED.value}{message}{Color.END.value}")

    @staticmethod
    def warning(message: str) -> None:
        print(f"{Color.YELLOW.value}{Color.BOLD.value}⚠ WARNING:{Color.END.value} "
              f"{Color.YELLOW.value}{message}{Color.END.value}")

    @staticmethod
    def info(message: str) -> None:
        print(f"{Color.GREEN_LIGHT.value}ℹ {message}{Color.END.value}")

    @staticmethod
    def step(current: int, total: int, message: str) -> None:
        """Log installation step with progress bar"""
        filled = int(current * 20 / total)
        bar = "█" * filled + "░" * (20 - filled)
        print(f"\n{Color.GREEN_BRIGHT.value}{Color.BOLD.value}[{current}/{total}]{Color.END.value} "
              f"{Color.GREEN_LIGHT.value}[{bar}]{Color.END.value} {message}")

    @staticmethod
    def section(title: str) -> None:
        """Print section header"""
        border = "═" * (len(title) + 4)
        print(f"\n{Color.BOLD.value}{Color.GREEN_BRIGHT.value}{border}")
        print(f"  {title}")
        print(f"{border}{Color.END.value}\n")

    @staticmethod
    def highlight(message: str) -> None:
        """Highlight important information"""
        print(f"{Color.HIGHLIGHT_BG.value}{Color.HIGHLIGHT_FG.value}{Color.BOLD.value} "
              f"{message} {Color.END.value}")

    @staticmethod
    def prompt(message: str) -> str:
        """Prompt user for input"""
        return input(f"{Color.YELLOW.value}{Color.BOLD.value}{message}{Color.END.value} ")

    @staticmethod
    def sudo_prompt(reason: str) -> None:
        """Show sudo requirement message"""
        print(f"\n{Color.BG_DARK_RED.value}{Color.WHITE.value}{Color.BOLD.value} "
              f"SUDO REQUIRED {Color.END.value}")
        print(f"{Color.RED.value}Reason: {reason}{Color.END.value}")
        print(f"{Color.YELLOW.value}Please enter your password when prompted.{Color.END.value}\n")


class CommandRunner:
    """Execute shell commands with various output modes"""

    @staticmethod
    def run(cmd: List[str], sudo: bool = False, capture: bool = False, 
            check: bool = False, reason: str = "") -> subprocess.CompletedProcess:
        """Execute command with optional sudo"""
        if sudo and shutil.which("sudo"):
            if reason:
                Logger.sudo_prompt(reason)
            cmd = ["sudo"] + cmd

        try:
            return subprocess.run(cmd, capture_output=capture, text=True, check=check)
        except FileNotFoundError:
            Logger.error(f"Command not found: {cmd[0]}")
            raise
        except subprocess.CalledProcessError as e:
            Logger.error(f"Command failed: {' '.join(cmd)}")
            raise

    @staticmethod
    def run_silent(cmd: List[str], sudo: bool = False, reason: str = "") -> int:
        """Run command silently, return exit code"""
        result = CommandRunner.run(cmd, sudo=sudo, capture=True, reason=reason)
        return result.returncode

    @staticmethod
    def run_with_progress(cmd: List[str], message: str, 
                         sudo: bool = False, reason: str = "") -> int:
        """Run command with progress indicator"""
        if sudo and shutil.which("sudo"):
            if reason:
                Logger.sudo_prompt(reason)
            cmd = ["sudo"] + cmd

        with ProgressIndicator(message):
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, 
                                     stderr=subprocess.DEVNULL)
            return process.wait()

    @staticmethod
    def run_with_output(cmd: List[str], sudo: bool = False, reason: str = "") -> int:
        """Run command showing inline output"""
        if sudo and shutil.which("sudo"):
            if reason:
                Logger.sudo_prompt(reason)
            cmd = ["sudo"] + cmd

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                  stderr=subprocess.STDOUT, text=True)

        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                print(f"\r{Color.GREEN_LIGHT.value} {line.strip()[:80]}...{Color.END.value}", 
                      end="", flush=True)

        process.wait()
        print("\r" + " " * 90 + "\r", end="", flush=True)
        return process.returncode


# ========== System Management ==========
class SystemManager:
    """System-level operations"""

    @staticmethod
    def update_system() -> bool:
        """Update system packages"""
        Logger.section("System Update")
        
        Logger.step(1, 2, "Updating package lists")
        if CommandRunner.run_with_output(
            ["apt-get", "update"], 
            sudo=True, 
            reason="Update package repository"
        ) != 0:
            Logger.error("Failed to update package lists")
            return False
        Logger.success("Package lists updated")

        Logger.step(2, 2, "Upgrading packages")
        if CommandRunner.run_with_output(
            ["apt-get", "upgrade", "-y"], 
            sudo=True, 
            reason="Upgrade system packages"
        ) != 0:
            Logger.error("Failed to upgrade packages")
            return False
        Logger.success("System upgraded")
        return True

    @staticmethod
    def install_packages(packages: List[str]) -> bool:
        """Install system packages"""
        if not packages:
            return True

        Logger.section("Package Installation")

        # Check installed packages
        result = CommandRunner.run(["dpkg-query", "-W", "-f=${Package}\n"], capture=True)
        installed = set(result.stdout.splitlines()) if result.returncode == 0 else set()

        to_install = [pkg for pkg in packages if pkg not in installed]
        already_installed = [pkg for pkg in packages if pkg in installed]

        if already_installed:
            Logger.success(f"Already installed: {', '.join(already_installed)}")

        if not to_install:
            return True

        Logger.info(f"Installing: {Color.YELLOW.value}{', '.join(to_install)}{Color.END.value}")

        if CommandRunner.run_with_output(
            ["apt-get", "install", "-y"] + to_install,
            sudo=True,
            reason=f"Install: {', '.join(to_install)}"
        ) != 0:
            Logger.error("Package installation failed")
            return False

        Logger.success(f"Installed: {', '.join(to_install)}")
        return True

    @staticmethod
    def create_systemd_service(config: NodeConfig) -> bool:
        """Create and enable systemd service"""
        service_name = "nym-node.service"
        service_path = f"/etc/systemd/system/{service_name}"
        
        # Get current user info
        result = CommandRunner.run(["whoami"], capture=True, check=True)
        user = result.stdout.strip()
        home_dir = str(Path.home())

        # Build command
        cmd_parts = [
            config.binary_path,
            "run",
            "--id", config.node_id,
            "--deny-init",
            "--mode", config.node_mode.value,
        ]

        if config.node_mode == NodeMode.EXIT_GATEWAY and config.wireguard_enabled:
            cmd_parts.extend(["--wireguard-enabled", "true"])

        cmd_parts.append("--accept-operator-terms-and-conditions")
        exec_cmd = " ".join(cmd_parts)

        # Create service content
        service_content = f"""[Unit]
Description=Nym Node ({config.node_id}) - {config.node_mode.value}
After=network.target
Wants=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={home_dir}
ExecStart={exec_cmd}
Restart=always
RestartSec=10
LimitNOFILE=65535

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=false
ReadWritePaths={home_dir}/.nym

[Install]
WantedBy=multi-user.target
"""

        try:
            # Write service file
            tmp_path = "/tmp/nym-node.service"
            with open(tmp_path, "w") as f:
                f.write(service_content)

            CommandRunner.run(["mv", tmp_path, service_path], sudo=True)
            CommandRunner.run(["chmod", "644", service_path], sudo=True)
            
            # Enable and start
            CommandRunner.run(["systemctl", "daemon-reload"], sudo=True)
            CommandRunner.run(["systemctl", "enable", service_name], sudo=True)
            CommandRunner.run(["systemctl", "start", service_name], sudo=True)
            
            Logger.success("Service created and started")
            return True

        except Exception as e:
            Logger.error(f"Service setup failed: {e}")
            return False


# ========== Network Management ==========
class NetworkManager:
    """Network operations"""

    @staticmethod
    def get_public_ip() -> Optional[str]:
        """Detect public IP address"""
        services = [
            "https://ifconfig.me/ip",
            "https://ipecho.net/plain",
            "https://icanhazip.com",
            "https://ident.me",
        ]

        for service in services:
            try:
                with urllib.request.urlopen(service, timeout=10) as response:
                    ip = response.read().decode().strip()
                    if ip and len(ip.split(".")) == 4:
                        Logger.success(f"Public IP: {Color.YELLOW.value}{ip}{Color.END.value}")
                        return ip
            except Exception:
                continue

        Logger.error("Failed to detect public IP")
        return None

    @staticmethod
    def configure_firewall(ports: List[int]) -> bool:
        """Configure UFW firewall"""
        Logger.section("Firewall Configuration")

        # Install UFW if needed
        if not shutil.which("ufw"):
            Logger.info("Installing UFW...")
            if not SystemManager.install_packages(["ufw"]):
                return False

        # Enable firewall
        result = CommandRunner.run(["ufw", "status"], capture=True)
        if "inactive" in result.stdout.lower():
            Logger.info("Enabling firewall...")
            CommandRunner.run(["ufw", "--force", "enable"], sudo=True)
            Logger.success("Firewall enabled")

        # Open ports
        success_count = 0
        for i, port in enumerate(ports, 1):
            Logger.step(i, len(ports), f"Opening port {port}")
            if CommandRunner.run_silent(["ufw", "allow", str(port)], sudo=True) == 0:
                success_count += 1
                Logger.success(f"Port {port} opened")
            else:
                Logger.error(f"Failed to open port {port}")

        if success_count == len(ports):
            Logger.success(f"All {len(ports)} ports configured")
            return True

        Logger.warning(f"Only {success_count}/{len(ports)} ports configured")
        return False


# ========== Nym Node Management ==========
class NymNodeManager:
    """Nym Node operations"""

    GITHUB_API = "https://api.github.com/repos/nymtech/nym/releases/latest"
    REQUIRED_PORTS = [8080, 1789, 1790, 9000]

    def __init__(self):
        self.config = NodeConfig()

    def check_existing_installation(self) -> bool:
        """Check if node is already installed"""
        nym_dir = Path.home() / ".nym"
        binary_exists = Path(self.config.binary_path).exists()
        return nym_dir.exists() or binary_exists

    def select_node_mode(self) -> None:
        """Interactive mode selection"""
        Logger.section("Node Mode Selection")

        print(f"{Color.BOLD.value}Available modes:{Color.END.value}")
        print(f"  {Color.CYAN.value}1.{Color.END.value} Mixnode - Privacy mixnode")
        print(f"  {Color.CYAN.value}2.{Color.END.value} Exit Gateway - Exit node")

        while True:
            choice = Logger.prompt("\nSelect mode (1 or 2): ").strip()

            if choice == "1":
                self.config.node_mode = NodeMode.MIXNODE
                self.config.wireguard_enabled = False
                Logger.success("Selected: Mixnode")
                break

            elif choice == "2":
                self.config.node_mode = NodeMode.EXIT_GATEWAY
                wg = Logger.prompt("Enable WireGuard? (y/N): ").strip().lower()
                self.config.wireguard_enabled = wg in ["y", "yes"]
                
                mode_desc = "Exit Gateway"
                if self.config.wireguard_enabled:
                    mode_desc += " with WireGuard"
                Logger.success(f"Selected: {mode_desc}")
                break
            else:
                Logger.error("Invalid choice")

    def download_binary(self) -> bool:
        """Download latest nym-node binary"""
        Logger.section("Binary Download")

        try:
            # Fetch release info
            with urllib.request.urlopen(self.GITHUB_API, timeout=30) as response:
                data = json.loads(response.read().decode())

            # Find binary URL
            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name", "").startswith("nym-node"):
                    download_url = asset.get("browser_download_url")
                    break

            if not download_url:
                Logger.error("Binary not found in release")
                return False

            # Download
            tmp_path = "/tmp/nym-node"
            with ProgressIndicator("Downloading binary"):
                urllib.request.urlretrieve(download_url, tmp_path)

            # Install
            CommandRunner.run(["mv", tmp_path, self.config.binary_path], sudo=True)
            CommandRunner.run(["chmod", "+x", self.config.binary_path], sudo=True)

            Logger.success(f"Binary installed: {self.config.binary_path}")
            return True

        except Exception as e:
            Logger.error(f"Download failed: {e}")
            return False

    def initialize_node(self) -> bool:
        """Initialize node configuration"""
        Logger.section("Node Initialization")

        # Get node ID
        while not self.config.node_id:
            node_id = Logger.prompt("Enter node ID (moniker): ").strip()
            if len(node_id) >= 3:
                self.config.node_id = node_id
            else:
                Logger.error("Node ID must be at least 3 characters")

        # Get public IP
        self.config.public_ip = NetworkManager.get_public_ip()
        if not self.config.public_ip:
            manual_ip = Logger.prompt("Enter public IP manually: ").strip()
            if manual_ip:
                self.config.public_ip = manual_ip
            else:
                return False

        # Run init
        try:
            cmd = [
                self.config.binary_path,
                "run",
                "--mode", self.config.node_mode.value,
                "--id", self.config.node_id,
                "--init-only",
                "--public-ips", self.config.public_ip,
                "--accept-operator-terms-and-conditions",
            ]

            if self.config.node_mode == NodeMode.EXIT_GATEWAY and self.config.wireguard_enabled:
                cmd.extend(["--wireguard-enabled", "true"])

            with ProgressIndicator("Initializing node"):
                subprocess.run(cmd, capture_output=True, text=True, check=True)

            Logger.success("Node initialized")
            return True

        except subprocess.CalledProcessError as e:
            Logger.error(f"Initialization failed: {e.stderr or str(e)}")
            return False

    def create_description(self) -> None:
        """Create node description file"""
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        desc_path = self.config.data_dir / "description.toml"

        Logger.info("Node description (optional):")
        website = Logger.prompt("Website: ").strip()
        security = Logger.prompt("Security contact: ").strip()
        details = Logger.prompt("Details: ").strip()

        content = f'''moniker = "{self.config.node_id}"
website = "{website}"
security_contact = "{security}"
details = "{details}"
'''

        try:
            with open(desc_path, "w") as f:
                f.write(content)
            Logger.success("Description created")
        except Exception as e:
            Logger.error(f"Description creation failed: {e}")

    def get_bonding_info(self) -> BondingInfo:
        """Get node bonding information"""
        try:
            result = subprocess.run(
                [self.config.binary_path, "bonding-information", "--id", self.config.node_id],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            info = BondingInfo(host=self.config.public_ip)
            for line in result.stdout.split("\n"):
                if "Identity Key:" in line:
                    info.identity_key = line.split(":", 1)[1].strip()
                elif "Host:" in line:
                    info.host = line.split(":", 1)[1].strip()

            return info

        except Exception as e:
            Logger.error(f"Failed to get bonding info: {e}")
            return BondingInfo()

    def load_mnemonic(self) -> str:
        """Load cosmos mnemonic from file"""
        mnemonic_path = self.config.data_dir / "cosmos_mnemonic"
        
        if not mnemonic_path.exists():
            Logger.error("Mnemonic file not found")
            return ""

        try:
            with open(mnemonic_path) as f:
                mnemonic = f.read().strip()
            self.config.cosmos_mnemonic = mnemonic
            return mnemonic
        except Exception as e:
            Logger.error(f"Failed to read mnemonic: {e}")
            return ""

    def sign_contract(self) -> None:
        """Sign contract message"""
        Logger.section("Contract Signing")

        bonding = self.get_bonding_info()
        if not bonding.identity_key:
            Logger.error("Cannot proceed without bonding info")
            return

        # Display bonding info
        Logger.highlight("BONDING INFORMATION")
        print(f"{Color.BOLD.value}Identity Key:{Color.END.value} "
              f"{Color.YELLOW.value}{bonding.identity_key}{Color.END.value}")
        print(f"{Color.BOLD.value}Host:{Color.END.value} "
              f"{Color.YELLOW.value}{bonding.host}{Color.END.value}")
        print(f"{Color.BOLD.value}Mode:{Color.END.value} "
              f"{Color.YELLOW.value}{self.config.node_mode.value}{Color.END.value}")

        Logger.info("\nInstructions:")
        Logger.info("1. Open Nym Wallet")
        Logger.info("2. Go to bonding section")
        Logger.info("3. Generate payload with info above")
        Logger.info("4. Paste payload below")

        # Get payload
        while True:
            print(f"\n{Color.YELLOW.value}Paste wallet payload:{Color.END.value}")
            payload = input(f"{Color.CYAN.value}> {Color.END.value}").strip()
            if len(payload) >= 10:
                break
            Logger.error("Invalid payload")

        # Sign
        try:
            cmd = [
                self.config.binary_path,
                "sign",
                "--id", self.config.node_id,
                "--contract-msg", payload,
            ]

            with ProgressIndicator("Signing contract"):
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            signature = self._extract_signature(result.stdout)
            
            if signature:
                Logger.success("Contract signed!")
                Logger.highlight("ENTER THIS IN WALLET")
                print(f"\n{Color.BG_GREEN.value}{Color.BOLD.value}{Color.RED.value} "
                      f"{signature} {Color.END.value}\n")

                while True:
                    if Logger.prompt("Copied signature? (yes/no): ").lower() in ["yes", "y"]:
                        Logger.success("Confirmed")
                        break
            else:
                Logger.highlight("SIGNATURE OUTPUT")
                print(f"{Color.GREEN_LIGHT.value}{result.stdout}{Color.END.value}")

        except subprocess.CalledProcessError as e:
            Logger.error(f"Signing failed: {e.stderr or str(e)}")

    @staticmethod
    def _extract_signature(output: str) -> Optional[str]:
        """Extract signature from command output"""
        if "is:\n" in output:
            return output.split("is:\n")[-1].strip()

        last_line = output.strip().split("\n")[-1].strip()
        if len(last_line) > 40:
            return last_line

        for line in output.split("\n"):
            if "is:" in line:
                return line.split("is:", 1)[-1].strip()

        return None


# ========== Wallet Management ==========
class WalletManager:
    """Wallet operations"""

    API_ENDPOINT = "https://api.nymtech.net/cosmos/bank/v1beta1/balances"
    MIN_BALANCE = 101.0

    @staticmethod
    def check_balance(address: str) -> Optional[float]:
        """Check NYX balance"""
        Logger.info(f"Checking balance: {Color.YELLOW.value}{address}{Color.END.value}")

        try:
            url = f"{WalletManager.API_ENDPOINT}/{address}"
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.loads(response.read().decode())

            # Parse balance
            balance_unym = 0
            for bal in data.get("balances", []):
                if bal.get("denom") == "unym":
                    balance_unym = int(bal.get("amount", "0"))
                    break

            balance_nym = balance_unym / 1_000_000

            # Display result
            if balance_nym >= WalletManager.MIN_BALANCE:
                Logger.success(f"Balance: {Color.GREEN_BRIGHT.value}{balance_nym:.6f} NYM{Color.END.value}")
            elif balance_nym > 0:
                Logger.warning(f"Balance: {Color.YELLOW.value}{balance_nym:.6f} NYM{Color.END.value} "
                             f"(need {WalletManager.MIN_BALANCE})")
            else:
                Logger.error(f"Balance: {Color.RED.value}0 NYM{Color.END.value} "
                           f"(need ≥{WalletManager.MIN_BALANCE})")

            return balance_nym

        except Exception as e:
            Logger.error(f"Balance check failed: {e}")
            return None

    @staticmethod
    def wait_for_funding(address: str) -> bool:
        """Wait for wallet to be funded"""
        while True:
            balance = WalletManager.check_balance(address)

            if balance is not None and balance >= WalletManager.MIN_BALANCE:
                Logger.success("Sufficient balance!")
                return True

            if balance is None:
                Logger.error("Could not check balance")
            else:
                Logger.warning(f"Insufficient: {balance:.6f} NYM")

            retry = Logger.prompt("Check again? (y/N): ").lower()
            if retry not in ["y", "yes"]:
                return False

            Logger.info("Waiting 10 seconds...")
            time.sleep(10)


# ========== Main Installer ==========
class NymNodeInstaller:
    """Main installation orchestrator"""

    def __init__(self, skip_update: bool = False):
        self.node_manager = NymNodeManager()
        self.steps = InstallationSteps(system_update=not skip_update)

    def run(self) -> None:
        """Run complete installation"""
        try:
            self._show_welcome()
            
            if not self._install():
                Logger.error("Installation failed")
                sys.exit(1)

            self._show_mnemonic()
            self._setup_wallet()
            self.node_manager.sign_contract()
            self._show_completion()

        except KeyboardInterrupt:
            Logger.warning("\nInterrupted by user")
            sys.exit(1)
        except Exception as e:
            Logger.error(f"Fatal error: {e}")
            sys.exit(1)

    def _show_welcome(self) -> None:
        """Display welcome message"""
        border = "─" * 40
        print(f"\n{Color.BOLD.value}{Color.GREEN_BRIGHT.value}{border}")
        print("    Nym Node Installer v3.0")
        print("    Enhanced & Refactored")
        print(f"{border}{Color.END.value}\n")

        Logger.info("This will:")
        print(f"  {Color.GREEN_BRIGHT.value}•{Color.END.value} Update system (optional)")
        print(f"  {Color.GREEN_BRIGHT.value}•{Color.END.value} Install dependencies")
        print(f"  {Color.GREEN_BRIGHT.value}•{Color.END.value} Configure Nym node")
        print(f"  {Color.GREEN_BRIGHT.value}•{Color.END.value} Setup systemd service\n")

        if not Logger.prompt("Continue? (y/N): ").lower().startswith("y"):
            Logger.info("Cancelled")
            sys.exit(0)

    def _install(self) -> bool:
        """Execute installation steps"""
        Logger.section("Installation")
        
        active_steps = [s for s, enabled in self.steps.get_active_steps() if enabled]
        total = len(active_steps)
        
        Logger.info(f"Executing {total} steps\n")

        try:
            step_num = 0

            # System update
            if self.steps.system_update:
                step_num += 1
                Logger.step(step_num, total, "System update")
                if not SystemManager.update_system():
                    return False

            # Dependencies
            step_num += 1
            Logger.step(step_num, total, "Dependencies")
            if not SystemManager.install_packages(["curl", "wget", "ufw"]):
                return False

            # Check existing installation
            if self.node_manager.check_existing_installation():
                Logger.warning("Existing installation detected")
                reinstall = Logger.prompt("Reinstall? (y/N): ")
                if not reinstall.lower().startswith("y"):
                    return False

            # Download binary
            step_num += 1
            Logger.step(step_num, total, "Binary download")
            if not self.node_manager.download_binary():
                return False

            # Mode selection
            step_num += 1
            Logger.step(step_num, total, "Mode selection")
            self.node_manager.select_node_mode()

            # Firewall
            step_num += 1
            Logger.step(step_num, total, "Firewall")
            if not NetworkManager.configure_firewall(NymNodeManager.REQUIRED_PORTS):
                Logger.warning("Firewall issues, continuing...")

            # Initialize
            step_num += 1
            Logger.step(step_num, total, "Node initialization")
            if not self.node_manager.initialize_node():
                return False
            self.node_manager.create_description()

            # Service
            step_num += 1
            Logger.step(step_num, total, "Service setup")
            if not SystemManager.create_systemd_service(self.node_manager.config):
                return False

            Logger.success("Installation complete!")
            return True

        except Exception as e:
            Logger.error(f"Installation failed: {e}")
            return False

    def _show_mnemonic(self) -> None:
        """Display mnemonic phrase"""
        Logger.section("Wallet Mnemonic")
        
        mnemonic = self.node_manager.load_mnemonic()
        if not mnemonic:
            return

        Logger.highlight("CRITICAL SECURITY")
        print(f"{Color.RED.value}{Color.BOLD.value}This is the ONLY way to recover your wallet!{Color.END.value}")
        print(f"{Color.RED.value}• Store securely{Color.END.value}")
        print(f"{Color.RED.value}• Never share{Color.END.value}")
        print(f"{Color.RED.value}• Write on paper{Color.END.value}\n")

        Logger.highlight("MNEMONIC PHRASE")
        print(f"{Color.BG_YELLOW.value}{Color.RED.value}{Color.BOLD.value} {mnemonic} {Color.END.value}\n")

        while True:
            confirmed = Logger.prompt("Safely stored? (yes/no): ")
            if confirmed.lower() in ["yes", "y"]:
                Logger.success("Confirmed")
                break

    def _setup_wallet(self) -> None:
        """Guide wallet setup and funding"""
        Logger.section("Wallet Setup")

        Logger.info("Steps:")
        print(f"  {Color.CYAN.value}1.{Color.END.value} Download: "
              f"{Color.GREEN_LIGHT.value}https://nym.com/wallet{Color.END.value}")
        print(f"  {Color.CYAN.value}2.{Color.END.value} Install wallet")
        print(f"  {Color.CYAN.value}3.{Color.END.value} Restore from mnemonic")
        print(f"  {Color.CYAN.value}4.{Color.END.value} Enter 24-word phrase")
        print(f"  {Color.CYAN.value}5.{Color.END.value} Fund with "
              f"{Color.YELLOW.value}101+ NYM{Color.END.value}\n")

        # Get wallet address
        while True:
            address = Logger.prompt("Enter wallet address (starts with 'n'): ").strip()
            if address.startswith("n") and len(address) > 10:
                break
            Logger.error("Invalid address format")

        # Wait for funding
        if not WalletManager.wait_for_funding(address):
            Logger.error("Cannot proceed without funds")
            sys.exit(1)

        input(f"\n{Color.CYAN.value}Press Enter to continue...{Color.END.value}")

    def _show_completion(self) -> None:
        """Show completion summary"""
        Logger.section("Installation Complete!")
        Logger.success("Nym node is running!")

        config = self.node_manager.config
        mode_desc = config.node_mode.value
        if config.node_mode == NodeMode.EXIT_GATEWAY and config.wireguard_enabled:
            mode_desc += " + WireGuard"

        print(f"\n{Color.BOLD.value}Installed:{Color.END.value}")
        print(f"  {Color.GREEN_BRIGHT.value}✓{Color.END.value} Binary: {config.binary_path}")
        print(f"  {Color.GREEN_BRIGHT.value}✓{Color.END.value} Node ID: "
              f"{Color.YELLOW.value}{config.node_id}{Color.END.value}")
        print(f"  {Color.GREEN_BRIGHT.value}✓{Color.END.value} Mode: "
              f"{Color.YELLOW.value}{mode_desc}{Color.END.value}")
        print(f"  {Color.GREEN_BRIGHT.value}✓{Color.END.value} Public IP: "
              f"{Color.YELLOW.value}{config.public_ip}{Color.END.value}")
        print(f"  {Color.GREEN_BRIGHT.value}✓{Color.END.value} Firewall configured")
        print(f"  {Color.GREEN_BRIGHT.value}✓{Color.END.value} Systemd service")
        print(f"  {Color.GREEN_BRIGHT.value}✓{Color.END.value} Contract signed")

        print(f"\n{Color.BOLD.value}Commands:{Color.END.value}")
        print(f"  Status: {Color.CYAN.value}sudo systemctl status nym-node{Color.END.value}")
        print(f"  Logs:   {Color.CYAN.value}sudo journalctl -u nym-node -f{Color.END.value}")
        print(f"  Stop:   {Color.CYAN.value}sudo systemctl stop nym-node{Color.END.value}")
        print(f"  Start:  {Color.CYAN.value}sudo systemctl start nym-node{Color.END.value}")

        Logger.highlight("Next Steps")
        Logger.info("1. Complete bonding in Nym Wallet")
        Logger.info("2. Wait for next epoch")
        Logger.info(f"3. Check: https://nymesis.vercel.app/?q={config.node_id}")

        print(f"\n{Color.BOLD.value}Support the Developer:{Color.END.value}")
        Logger.info("Delegate to nodes:")
        nodes = [
            "8jFCkcCJus7cHg8LVQiTwbEuKqzmMm6EwYezNx2cKArB",
            "EmUjBBYcvNzEovM7AhxrYXeTJJ4Kg2g2w7sP6V1GDa13",
            "CRzMQu3Fbf3eGCscPog323gofAGWzT37gXuvWEFHm9NG",
            "G2adZrt5ByjSZKrR6G139FYfd4ScxHbinQjpP28h4APm",
            "E3BayLcp2RiQ66ZxzkPkZuREYCYrsHB1o7vFULQ6u6Np",
            "F618gw6jZaLR1VdMTeaH11MhHQJY5rdpYEDLrMKEHcjk",
        ]
        for node in nodes:
            print(f"  • {Color.CYAN.value}{node}{Color.END.value}")
        
        print(f"\n{Color.YELLOW.value}Donate NYM: "
              f"n18lc3qmx4jqzr55gvh5qmg6z3q4874x4xmmhhqd{Color.END.value}\n")


# ========== CLI Entry Point ==========
def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Nym Node Installer v3.0 - Refactored Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 nym_installer.py
  python3 nym_installer.py --no-update
  
Features:
  • Automatic mode selection (mixnode/exit-gateway)
  • Optional WireGuard support
  • Systemd service setup
  • Wallet integration
  • Contract signing
        """
    )
    
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="Skip system update step"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Nym Node Installer v3.0"
    )
    
    args = parser.parse_args()

    # Platform check
    if sys.platform != "linux":
        Logger.error("Linux only")
        sys.exit(1)

    # Python version check
    if sys.version_info < (3, 6):
        Logger.error("Python 3.6+ required")
        sys.exit(1)

    # Run installer
    try:
        installer = NymNodeInstaller(skip_update=args.no_update)
        installer.run()
    except Exception as e:
        Logger.error(f"Fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
