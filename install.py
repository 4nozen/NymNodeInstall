#!/usr/bin/env python3
"""
Nym Node Installer - Automated installation and configuration of a Nym Node
Refactored version without external dependencies
"""

import os
import sys
import json
import time
import argparse
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import threading
import shutil
import getpass

@dataclass
class NodeConfig:
    """Node Configuration"""
    node_id: str = ""
    public_ip: str = ""
    binary_path: str = ""
    cosmos_mnemonic: str = ""
    nyx_address: str = ""
    rpc_endpoint: str = "https://nym-rpc.polkachu.com/"

class Colors:
    """ANSI colors for terminal output"""
    # Main Theme Colors (Green Tones)
    GREEN_BRIGHT = '\033[92m'
    GREEN_LIGHT = '\033[38;5;42m'
    
    # Accent & Status Colors
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    # Special Highlight Colors
    HIGHLIGHT_BG = '\033[48;5;22m' # Dark Green BG
    HIGHLIGHT_FG = '\033[38;5;154m' # Bright Green FG
    
    # Text Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

    # Background colors for important messages
    BG_RED = '\033[101m'
    BG_YELLOW = '\033[103m'
    BG_GREEN_BRIGHT = '\033[102m'

class ProgressIndicator:
    """Progress indicator for long-running operations"""
    
    def __init__(self, message: str, spinner_chars: str = '|/-\"' ):
        self.message = message
        self.spinner_chars = spinner_chars
        self.running = False
        self.thread = None
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        
    def start(self):
        """Start the progress indicator"""
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self, success_msg: str = None):
        """Stop the progress indicator"""
        self.running = False
        if self.thread:
            self.thread.join()
        # Clear the line
        print('\r' + ' ' * (len(self.message) + 10) + '\r', end='', flush=True)
        if success_msg:
            Logger.success(success_msg)
            
    def _spin(self):
        """Spinning animation"""
        idx = 0
        while self.running:
            char = self.spinner_chars[idx % len(self.spinner_chars)]
            print(f'\r{Colors.GREEN_LIGHT}{char} {self.message}...{Colors.END}', end='', flush=True)
            time.sleep(0.1)
            idx += 1

class Logger:
    """Enhanced logging utilities with beautiful output"""

    @staticmethod
    def success(message: str) -> None:
        """Print success message"""
        print(f"{Colors.GREEN_BRIGHT}{Colors.BOLD}SUCCESS:{Colors.END} {Colors.GREEN_LIGHT}{message}{Colors.END}")

    @staticmethod
    def error(message: str) -> None:
        """Print error message"""
        print(f"{Colors.RED}{Colors.BOLD}ERROR:{Colors.END} {Colors.RED}{message}{Colors.END}")

    @staticmethod
    def warning(message: str) -> None:
        """Print warning message"""
        print(f"{Colors.YELLOW}{Colors.BOLD}WARNING:{Colors.END} {Colors.YELLOW}{message}{Colors.END}")

    @staticmethod
    def info(message: str) -> None:
        """Print info message"""
        print(f"{Colors.GREEN_LIGHT}{Colors.BOLD}INFO:{Colors.END} {Colors.GREEN_LIGHT}{message}{Colors.END}")

    @staticmethod
    def debug(message: str) -> None:
        """Print debug message"""
        print(f"{Colors.DIM}DEBUG: {message}{Colors.END}")

    @staticmethod
    def step(step_num: int, total_steps: int, message: str) -> None:
        """Print step message"""
        progress = "█" * (step_num * 20 // total_steps) + "░" * (20 - (step_num * 20 // total_steps))
        print(f"{Colors.GREEN_BRIGHT}{Colors.BOLD}[{step_num}/{total_steps}]{Colors.END} "
              f"{Colors.GREEN_LIGHT}[{progress}]{Colors.END} {message}")

    @staticmethod
    def section(title: str) -> None:
        """Print section header"""
        border = "═" * (len(title) + 4)
        print(f"\n{Colors.BOLD}{Colors.GREEN_BRIGHT}{border}")
        print(f"  {title}")
        print(f"{border}{Colors.END}\n")

    @staticmethod
    def highlight(message: str) -> None:
        """Print highlighted message"""
        print(f"{Colors.HIGHLIGHT_BG}{Colors.HIGHLIGHT_FG}{Colors.BOLD} {message} {Colors.END}")

    @staticmethod
    def prompt(message: str) -> str:
        """Get user input with styled prompt"""
        return input(f"{Colors.YELLOW}{Colors.BOLD}{message}{Colors.END} ")

    @staticmethod
    def sudo_prompt(reason: str) -> None:
        """Explain why sudo is needed"""
        print(f"\n{Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} SUDO REQUIRED {Colors.END}")
        print(f"{Colors.RED}Reason: {reason}{Colors.END}")
        print(f"{Colors.YELLOW}Please enter your password when prompted.{Colors.END}\n")

class CommandRunner:
    """Enhanced command execution utilities"""

    @staticmethod
    def check_sudo_available() -> bool:
        """Check if sudo is available"""
        return shutil.which('sudo') is not None

    @staticmethod
    def run(cmd: List[str], sudo: bool = False, capture_output: bool = False,
            text: bool = True, check: bool = False, sudo_reason: str = "") -> subprocess.CompletedProcess:
        """Execute a command with optional sudo"""
        if sudo and CommandRunner.check_sudo_available():
            if sudo_reason:
                Logger.sudo_prompt(sudo_reason)
            cmd = ['sudo'] + cmd
        elif sudo:
            Logger.error("sudo is not available on this system")
            raise RuntimeError("sudo not available")
            
        try:
            return subprocess.run(cmd, capture_output=capture_output, text=text, check=check)
        except FileNotFoundError:
            Logger.error(f"Command not found: {cmd[0] if cmd else 'unknown'}")
            raise

    @staticmethod
    def run_with_progress(cmd: List[str], progress_msg: str, sudo: bool = False, 
                         sudo_reason: str = "") -> int:
        """Execute a command with progress indicator"""
        if sudo and CommandRunner.check_sudo_available():
            if sudo_reason:
                Logger.sudo_prompt(sudo_reason)
            cmd = ['sudo'] + cmd

        try:
            with ProgressIndicator(progress_msg):
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
                return process.wait()
        except FileNotFoundError:
            Logger.error(f"Command not found: {cmd[0] if cmd else 'unknown'}")
            return 1

    @staticmethod
    def run_with_inline_output(cmd: List[str], sudo: bool = False, sudo_reason: str = "") -> int:
        """Execute a command with inline output (single line)"""
        if sudo and CommandRunner.check_sudo_available():
            if sudo_reason:
                Logger.sudo_prompt(sudo_reason)
            cmd = ['sudo'] + cmd

        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                universal_newlines=True
            )
            
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    # Clear line and show current progress
                    print(f'\n{Colors.GREEN_LIGHT} {line.strip()[:80]}...{Colors.END}', end='', flush=True)
                    
            process.wait()
            print('\r' + ' ' * 90 + '\r', end='', flush=True)  # Clear line
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)
            return process.returncode
            
        except FileNotFoundError:
            Logger.error(f"Command not found: {cmd[0] if cmd else 'unknown'}")
            return 1

class SystemManager:
    """System management with improved UX"""

    @staticmethod
    def update_system() -> bool:
        """Update the system with progress indication"""
        Logger.section("Updating System Packages")

        try:
            # Update package list
            Logger.step(1, 2, "Updating package repository information")
            result = CommandRunner.run_with_inline_output(
                ['apt-get', 'update'], 
                sudo=True, 
                sudo_reason="Update package repository information"
            )
            if result != 0:
                Logger.error("Failed to update package lists")
                return False
            Logger.success("Package lists updated")

            # Upgrade packages
            Logger.step(2, 2, "Upgrading system packages")
            result = CommandRunner.run_with_inline_output(
                ['apt-get', 'upgrade', '-y'], 
                sudo=True, 
                sudo_reason="Upgrade system packages"
            )
            if result != 0:
                Logger.error("Failed to upgrade packages")
                return False
            Logger.success("System packages upgraded")

            Logger.success("System update completed successfully!")
            return True
            
        except subprocess.CalledProcessError as e:
            Logger.error(f"System update failed: {e}")
            return False
        except Exception as e:
            Logger.error(f"Unexpected error during system update: {e}")
            return False

    @staticmethod
    def install_packages(packages: List[str]) -> bool:
        """Install packages with detailed feedback"""
        Logger.section(f"Installing Required Packages")
        
        if not packages:
            Logger.info("No packages to install")
            return True

        try:
            # Check which packages are already installed
            Logger.info("Checking installed packages...")
            try:
                result = CommandRunner.run(['dpkg-query', '-W', '-f=${Package}\n'],
                                         capture_output=True, check=True)
                installed = set(result.stdout.splitlines())
            except subprocess.CalledProcessError:
                installed = set()

            to_install = [pkg for pkg in packages if pkg not in installed]
            already_installed = [pkg for pkg in packages if pkg in installed]

            if already_installed:
                Logger.success(f"Already installed: {', '.join(already_installed)}")

            if not to_install:
                Logger.success("All required packages are already installed")
                return True

            Logger.info(f"Installing: {Colors.YELLOW}{', '.join(to_install)}{Colors.END}")
            
            result = CommandRunner.run_with_inline_output(
                ['apt-get', 'install', '-y'] + to_install, 
                sudo=True, 
                sudo_reason=f"Install packages: {', '.join(to_install)}"
            )
            
            if result == 0:
                Logger.success(f"Successfully installed: {', '.join(to_install)}")
                return True
            else:
                Logger.error("Package installation failed")
                return False
                
        except Exception as e:
            Logger.error(f"Package installation error: {e}")
            return False

class NetworkManager:
    """Network management without external dependencies"""

    @staticmethod
    def get_public_ip() -> Optional[str]:
        """Get public IP address using urllib"""
        services = [
            "https://ifconfig.me/ip",
            "https://ipecho.net/plain",
            "https://icanhazip.com",
            "https://ident.me",
        ]
        
        Logger.info("Detecting public IP address...")
        
        for service in services:
            try:
                with urllib.request.urlopen(service, timeout=10) as response:
                    ip = response.read().decode().strip()
                    if ip and len(ip.split('.')) == 4:  # Basic IPv4 validation
                        Logger.success(f"Public IP detected: {Colors.YELLOW}{ip}{Colors.END}")
                        return ip
            except Exception:
                continue
                
        Logger.error("Failed to detect public IP address")
        return None

    @staticmethod
    def open_ports(ports: List[int]) -> bool:
        """Open ports using ufw with detailed feedback"""
        Logger.section(f"Configuring Firewall")
        
        try:
            # Check if ufw exists
            if not shutil.which('ufw'):
                Logger.info("ufw not found, installing...")
                if not SystemManager.install_packages(['ufw']):
                    Logger.error("Failed to install ufw")
                    return False

            # Check ufw status
            try:
                result = CommandRunner.run(['ufw', 'status'], capture_output=True, check=True)
                status_output = result.stdout
            except subprocess.CalledProcessError:
                Logger.error("Failed to check ufw status")
                return False

            # Enable ufw if inactive
            if "inactive" in status_output.lower():
                Logger.info("Enabling firewall...")
                result = CommandRunner.run(
                    ['ufw', '--force', 'enable'], 
                    sudo=True, 
                    sudo_reason="Enable firewall (ufw)"
                )
                if result.returncode != 0:
                    Logger.error("Failed to enable ufw")
                    return False
                Logger.success("Firewall enabled")

            # Open required ports
            success_count = 0
            for i, port in enumerate(ports, 1):
                Logger.step(i, len(ports), f"Opening port {port}")
                result = CommandRunner.run(
                    ['ufw', 'allow', str(port)], 
                    sudo=True, 
                    sudo_reason=f"Open port {port}"
                )
                if result.returncode == 0:
                    success_count += 1
                    Logger.success(f"Port {port} opened successfully")
                else:
                    Logger.error(f"Failed to open port {port}")

            if success_count == len(ports):
                Logger.success(f"All {len(ports)} ports configured successfully")
                return True
            else:
                Logger.warning(f"Only {success_count}/{len(ports)} ports were configured")
                return False

        except Exception as e:
            Logger.error(f"Firewall configuration error: {e}")
            return False

class NymNodeManager:
    """Enhanced Nym Node management"""

    def __init__(self):
        self.config = NodeConfig()
        self.dest_dir = Path.home() / "nym"
        self.dest_dir.mkdir(exist_ok=True)

    def check_if_node_installed(self) -> bool:
        """Check if node is already installed"""
        nym_dir = Path.home() / ".nym"
        binary_exists = Path("/usr/local/bin/nym-node").exists()
        
        if nym_dir.exists():
            Logger.info(f"Found existing Nym configuration in: {nym_dir}")
        if binary_exists:
            Logger.info("Found existing nym-node binary")
            
        return nym_dir.exists() or binary_exists

    def download_latest_binary(self) -> str:
        """Download the latest binary using urllib"""
        Logger.section("Downloading Nym Node Binary")

        api_url = "https://api.github.com/repos/nymtech/nym/releases/latest"
        
        try:
            Logger.info("Fetching latest release information...")
            with urllib.request.urlopen(api_url, timeout=30) as response:
                data = json.loads(response.read().decode())
                
        except Exception as e:
            Logger.error(f"Failed to fetch release information: {e}")
            return ""

        download_url = None
        for asset in data.get("assets", []):
            if asset.get("name", "").startswith("nym-node"):
                download_url = asset.get("browser_download_url")
                break

        if not download_url:
            Logger.error("Could not find nym-node binary in the latest release")
            return ""

        tmp_path = "/tmp/nym-node"
        binary_dest_path = "/usr/local/bin/nym-node"
        
        try:
            Logger.info(f"Downloading binary from: {download_url}")
            
            # Download with progress
            with ProgressIndicator("Downloading nym-node binary"):
                urllib.request.urlretrieve(download_url, tmp_path)
            Logger.success("Binary downloaded successfully")
            
            # Move and set permissions
            Logger.info("Installing binary...")
            result = CommandRunner.run(
                ['mv', tmp_path, binary_dest_path], 
                sudo=True, 
                sudo_reason="Install nym-node binary to /usr/local/bin"
            )
            if result.returncode != 0:
                Logger.error("Failed to move binary")
                return ""
                
            result = CommandRunner.run(
                ['chmod', '+x', binary_dest_path], 
                sudo=True, 
                sudo_reason="Make nym-node binary executable"
            )
            if result.returncode != 0:
                Logger.error("Failed to make binary executable")
                return ""
            
            Logger.success(f"Binary installed: {Colors.YELLOW}{binary_dest_path}{Colors.END}")
            self.config.binary_path = binary_dest_path
            return binary_dest_path
            
        except Exception as e:
            Logger.error(f"Binary installation failed: {e}")
            return ""

    def initialize_node(self) -> bool:
        """Initialize the node with enhanced UX"""
        Logger.section("Node Initialization")

        # Get node ID
        while not self.config.node_id:
            self.config.node_id = Logger.prompt("Enter your unique node ID: ").strip()
            if not self.config.node_id:
                Logger.error("Node ID cannot be empty!")
            elif len(self.config.node_id) < 3:
                Logger.error("Node ID must be at least 3 characters long!")
                self.config.node_id = ""
            else:
                Logger.success(f"Node ID set: {Colors.YELLOW}{self.config.node_id}{Colors.END}")

        # Get public IP
        self.config.public_ip = NetworkManager.get_public_ip()
        if not self.config.public_ip:
            manual_ip = Logger.prompt("Could not detect IP. Enter manually (or press Enter to retry): ")
            if manual_ip.strip():
                self.config.public_ip = manual_ip.strip()
            else:
                return False

        # Initialize node
        Logger.info("Initializing Nym node...")
        try:
            with ProgressIndicator("Initializing node configuration"):
                result = subprocess.run([
                    self.config.binary_path,
                    "run",
                    "--mode", "mixnode",
                    "--id", self.config.node_id,
                    "--init-only",
                    "--public-ips", self.config.public_ip,
                    "--accept-operator-terms-and-conditions"
                ], capture_output=True, text=True, check=True)
                
            Logger.success("Node initialized successfully!")
            return True
            
        except subprocess.CalledProcessError as e:
            Logger.error(f"Node initialization failed: {e}")
            if e.stderr:
                Logger.debug(f"Error details: {e.stderr}")
            return False

    def create_description_toml(self) -> str:
        """Create description.toml file with better UX"""
        Logger.section("Node Description Configuration")

        base_dir = Path.home() / ".nym" / "nym-nodes" / self.config.node_id / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        file_path = base_dir / "description.toml"

        Logger.info("Configure your node description (optional, press Enter to skip):")
        
        website = Logger.prompt("Website URL: ").strip()
        security_contact = Logger.prompt("Security contact email: ").strip()
        details = Logger.prompt("Node description/details: ").strip()

        content = f'''moniker = "{self.config.node_id}"
website = "{website}"
security_contact = "{security_contact}"
details = "{details}"
'''

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            Logger.success(f"Description file created: {Colors.YELLOW}{file_path}{Colors.END}")
            return str(file_path)
        except Exception as e:
            Logger.error(f"Failed to create description file: {e}")
            return ""

    def create_systemd_service(self) -> bool:
        """Create systemd service with proper user handling"""
        Logger.section("Setting up System Service")

        if not self.config.node_id:
            Logger.error("Node ID is not set!")
            return False

        service_name = "nym-node.service"
        service_path = f"/etc/systemd/system/{service_name}"
        
        # Get the actual username (not root when using sudo)
        current_user = os.getenv("SUDO_USER") or os.getenv("USER") or getpass.getuser()

        service_content = f"""
[Unit]
Description=Nym Node ({self.config.node_id})
After=network.target
Wants=network.target

[Service]
Type=simple
User={current_user}
ExecStart={self.config.binary_path} run --mode mixnode --id {self.config.node_id} --accept-operator-terms-and-conditions
Restart=always
RestartSec=10
LimitNOFILE=65535

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=false
ReadWritePaths=/home/{current_user}/.nym

[Install]
WantedBy=multi-user.target
"""

        try:
            tmp_service = "/tmp/nym-node.service"
            with open(tmp_service, "w") as f:
                f.write(service_content)

            Logger.info("Installing systemd service...")
            result = CommandRunner.run(
                ['mv', tmp_service, service_path], 
                sudo=True, 
                sudo_reason="Install systemd service file"
            )
            if result.returncode != 0:
                Logger.error("Failed to install service file")
                return False

            CommandRunner.run(
                ['chmod', '644', service_path], 
                sudo=True, 
                sudo_reason="Set correct permissions on service file"
            )

            Logger.info("Configuring systemd...")
            CommandRunner.run(
                ['systemctl', 'daemon-reload'], 
                sudo=True, 
                sudo_reason="Reload systemd configuration"
            )
            
            CommandRunner.run(
                ['systemctl', 'enable', service_name], 
                sudo=True, 
                sudo_reason="Enable nym-node service to start on boot"
            )
            
            CommandRunner.run(
                ['systemctl', 'start', service_name], 
                sudo=True, 
                sudo_reason="Start nym-node service"
            )

            Logger.success(f"Service {Colors.YELLOW}{service_name}{Colors.END} is running and enabled")
            return True
            
        except Exception as e:
            Logger.error(f"Service setup failed: {e}")
            return False

    def get_bonding_information(self) -> Dict[str, str]:
        """Get bonding information with better error handling"""
        Logger.info("Retrieving node bonding information...")
        
        try:
            result = subprocess.run([
                self.config.binary_path,
                "bonding-information",
                "--id", self.config.node_id
            ], capture_output=True, check=True, text=True, timeout=30)

            bonding_info = {}
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if "Identity Key:" in line:
                    bonding_info["identity_key"] = line.split(":", 1)[1].strip()
                elif "Host:" in line:
                    bonding_info["host"] = line.split(":", 1)[1].strip()
            
            # Fallback to configured IP if host not found
            if not bonding_info.get("host"):
                bonding_info["host"] = self.config.public_ip

            if bonding_info.get("identity_key"):
                Logger.success("Bonding information retrieved successfully")
            else:
                Logger.warning("Could not extract identity key from output")
                
            return bonding_info

        except subprocess.CalledProcessError as e:
            Logger.error(f"Failed to get bonding information: {e}")
            return {}
        except Exception as e:
            Logger.error(f"Unexpected error getting bonding information: {e}")
            return {}

    def get_cosmos_mnemonic(self) -> str:
        """Get cosmos mnemonic with better error handling"""
        mnemonic_path = Path.home() / ".nym" / "nym-nodes" / self.config.node_id / "data" / "cosmos_mnemonic"

        if not mnemonic_path.exists():
            Logger.error("Cosmos mnemonic file not found. Ensure the node is properly initialized.")
            return ""

        try:
            with open(mnemonic_path, 'r') as f:
                mnemonic = f.read().strip()

            if not mnemonic:
                Logger.error("Mnemonic file is empty")
                return ""

            # Basic validation - should be 24 words
            words = mnemonic.split()
            if len(words) != 24:
                Logger.warning(f"Unusual mnemonic length: {len(words)} words (expected 24)")

            self.config.cosmos_mnemonic = mnemonic
            return mnemonic
            
        except Exception as e:
            Logger.error(f"Error reading cosmos mnemonic: {e}")
            return ""

    def check_balance(self, address: str) -> Optional[Dict[str, Any]]:
        """Check NYX account balance using urllib and return detailed info"""
        Logger.info(f"Checking account balance for: {Colors.YELLOW}{address}{Colors.END}")
        
        try:
            api_url = f"https://validator.nymtech.net/api/v1/unstable/account/{address}"
            
            with urllib.request.urlopen(api_url, timeout=15) as response:
                data = json.loads(response.read().decode())

            balance_unym = 0
            # for coin in data.get('balances', []):
            #     if coin.get('denom') == 'unym':
            #         balance_unym = int(coin.get('amount', 0))
            #         break
            # balance_unym = int(data.get('balance', 0))

            # Проверка наличия ключей
            if "balance" in data and "amount" in data["balance"]:
                balance_unym = int(data["balance"]["amount"])
            else:
                balance_unym = 0  # Значение по умолчанию
            
            balance_nym = balance_unym / 1_000_000
            
            if balance_nym >= 101:
                Logger.success(f"Current balance: {Colors.GREEN_BRIGHT}{balance_nym:.6f} NYM{Colors.END}")
            elif balance_nym > 0:
                Logger.warning(f"Current balance: {Colors.YELLOW}{balance_nym:.6f} NYM{Colors.END} (need 101 NYM)")
            else:
                Logger.error(f"Current balance: {Colors.RED}{balance_nym:.6f} NYM{Colors.END} (need ≥101 NYM)")
            
            return balance_nym

        except Exception as e:
            Logger.error(f"Failed to check balance: {e}")
            return None

    def sign_contract_message(self) -> None:
        """Sign the contract message with enhanced UX"""
        Logger.section("Contract Message Signing")

        bonding_info = self.get_bonding_information()
        if not bonding_info or not bonding_info.get("identity_key"):
            Logger.error("Cannot proceed without bonding information")
            return

        # Display bonding information
        Logger.highlight("BONDING INFORMATION FOR WALLET")
        print(f"{Colors.BOLD}Identity Key:{Colors.END} {Colors.YELLOW}{bonding_info['identity_key']}{Colors.END}")
        print(f"{Colors.BOLD}Host:{Colors.END} {Colors.YELLOW}{bonding_info['host']}{Colors.END}")
        
        Logger.info("\nInstructions:")
        Logger.info("1. Open the Nym Wallet application")
        Logger.info("2. Go to the bonding section")
        Logger.info("3. Use the information above to generate the payload")
        Logger.info("4. Copy the generated payload and paste it below")
        Logger.info("\nDocumentation: https://nym.com/docs/operators/nodes/nym-node/bonding#bond-via-the-desktop-wallet-recommended")
        
        # Get payload from user
        while True:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}Please paste the payload generated by the wallet:{Colors.END}")
            Logger.highlight("PASTE PAYLOAD HERE")
            payload = input(f"{Colors.CYAN}> {Colors.END}").strip()
            
            if payload:
                # Basic validation
                if len(payload) < 10:
                    Logger.error("Payload seems too short. Please check and try again.")
                    continue
                break
            else:
                Logger.error("Payload cannot be empty!")

        # Sign the payload
        try:
            Logger.info("Signing contract message...")
            cmd = [self.config.binary_path, "sign", "--id", self.config.node_id, "--contract-msg", payload]
            
            with ProgressIndicator("Processing signature"):
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if result.stdout:
                # Extract signature from output
                signature = self._extract_signature(result.stdout)
                
                if signature:
                    Logger.success("Contract message signed successfully!")
                    Logger.highlight("ENTER THIS SIGNATURE IN YOUR WALLET")
                    print(f"\n{Colors.BG_GREEN_BRIGHT}{Colors.WHITE}{Colors.BOLD} {signature} {Colors.END}\n")
                    
                    Logger.info("Next steps:")
                    Logger.info("1. Copy the signature above")
                    Logger.info("2. Return to your Nym Wallet")
                    Logger.info("3. Paste this signature in the 'Signature' field")
                    Logger.info("4. Complete the bonding transaction")
                    
                    # Ask user to confirm they've copied it
                    while True:
                        confirmed = Logger.prompt("Have you copied the signature to your wallet? (yes/no): ")
                        if confirmed.lower() in ['yes', 'y']:
                            Logger.success("Signature confirmed as copied")
                            break
                        elif confirmed.lower() in ['no', 'n']:
                            Logger.info("Please copy the signature before continuing")
                            Logger.highlight("SIGNATURE TO COPY")
                            print(f"{Colors.BG_GREEN_BRIGHT}{Colors.WHITE}{Colors.BOLD} {signature} {Colors.END}")
                            continue
                        else:
                            Logger.error("Please answer 'yes' or 'no'")
                else:
                    Logger.warning("Could not extract signature from output")
                    Logger.highlight("FULL SIGNATURE OUTPUT")
                    print(f"{Colors.GREEN_LIGHT}{result.stdout}{Colors.END}")
            else:
                Logger.warning("No signature output received")

        except subprocess.CalledProcessError as e:
            Logger.error(f"Signing failed: {e}")
            if e.stderr:
                Logger.debug(f"Error details: {e.stderr}")

    def _extract_signature(self, output: str) -> Optional[str]:
        """Extract signature from nym-node sign command output"""
        try:
            # Look for the line that contains "is:"
            lines = output.strip().split('\n')
            for line in lines:
                if 'is:' in line:
                    # Extract everything after "is:"
                    signature = line.split('is:', 1)[1].strip()
                    if signature:
                        Logger.debug(f"Extracted signature: {signature}")
                        return signature
            
            # Fallback: look for base58-like strings (last line that looks like a signature)
            for line in reversed(lines):
                line = line.strip()
                # Base58 signatures are typically long alphanumeric strings
                if len(line) > 40 and line.replace(' ', '').isalnum():
                    Logger.debug(f"Fallback signature extraction: {line}")
                    return line
                    
            Logger.debug("Could not find signature pattern in output")
            return None
            
        except Exception as e:
            Logger.error(f"Error extracting signature: {e}")
            return None

class NymNodeInstaller:
    """Main installer class with enhanced workflow"""

    def __init__(self):
        self.node_manager = NymNodeManager()

    def run(self, no_update: bool = False):
        """Run the installer with enhanced user experience"""
        try:
            self._print_welcome()
            
            if not self._install_node(no_update=no_update):
                Logger.error("Installation failed!")
                sys.exit(1)

            self._show_mnemonic()
            self._guide_wallet_setup()
            self.node_manager.sign_contract_message()
            self._show_completion()

        except KeyboardInterrupt:
            Logger.warning("\nInstallation interrupted by user")
            Logger.info("You can run this script again to continue the installation")
            sys.exit(1)
        except Exception as e:
            Logger.error(f"Unexpected error: {e}")
            Logger.debug(f"Error type: {type(e).__name__}")
            sys.exit(1)

    def _print_welcome(self):
        """Print welcome message"""
        border = "─" * 40
        print(f"\n{Colors.BOLD}{Colors.GREEN_BRIGHT}{border}")
        print(f"    Welcome to the Nym Node Installer!")
        print(f"         Enhanced & User-Friendly")
        print(f"{border}{Colors.END}\n")
        
        Logger.info("This installer will:")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Update your system (optional)")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Install required dependencies")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Download and configure Nym node")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Set up systemd service")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Generate wallet credentials")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Help with bonding process")
        
        print(f"\n{Colors.YELLOW}You'll be prompted for sudo password when needed{Colors.END}")
        
        if not Logger.prompt("Continue? (y/N): ").lower().startswith('y'):
            Logger.info("Installation cancelled by user")
            sys.exit(0)

    def _install_node(self, no_update: bool = False) -> bool:
        """Full node installation with progress tracking"""
        Logger.section("Node Installation Process")

        steps = [
            ("System Update", not no_update),
            ("Dependency Installation", True),
            ("Binary Download", True),
            ("Firewall Configuration", True),
            ("Node Initialization", True),
            ("Service Setup", True)
        ]
        
        active_steps = [step for step, enabled in steps if enabled]
        Logger.info(f"Installation will complete {len(active_steps)} steps\n")

        try:
            step_num = 0
            
            # Step 1: System Update (optional)
            if not no_update:
                step_num += 1
                Logger.step(step_num, len(active_steps), "Updating system packages")
                if not SystemManager.update_system():
                    Logger.error("System update failed")
                    return False
            else:
                Logger.info("Skipping system update as requested")

            # Step 2: Install dependencies
            step_num += 1
            Logger.step(step_num, len(active_steps), "Installing dependencies")
            if not SystemManager.install_packages(['curl', 'wget']):
                Logger.error("Dependency installation failed")
                return False

            # Check for reinstallation
            if self.node_manager.check_if_node_installed():
                Logger.warning("Existing Nym node installation detected")
                reinstall = Logger.prompt("Reinstall? This will overwrite existing configuration (y/N): ")
                if not reinstall.lower().startswith('y'):
                    Logger.info("Installation cancelled")
                    return False
                Logger.info("Proceeding with reinstallation...")

            # Step 3: Download binary
            step_num += 1
            Logger.step(step_num, len(active_steps), "Downloading Nym node binary")
            if not self.node_manager.download_latest_binary():
                Logger.error("Binary download failed")
                return False

            # Step 4: Configure firewall
            step_num += 1
            Logger.step(step_num, len(active_steps), "Configuring firewall")
            required_ports = [8080, 1789, 1790, 9000]
            if not NetworkManager.open_ports(required_ports):
                Logger.warning("Firewall configuration had issues, but continuing...")

            # Step 5: Initialize node
            step_num += 1
            Logger.step(step_num, len(active_steps), "Initializing node")
            if not self.node_manager.initialize_node():
                Logger.error("Node initialization failed")
                return False

            # Create description file
            self.node_manager.create_description_toml()

            # Step 6: Setup service
            step_num += 1
            Logger.step(step_num, len(active_steps), "Setting up system service")
            if not self.node_manager.create_systemd_service():
                Logger.error("Service setup failed")
                return False

            Logger.success("Node installation completed successfully!")
            return True

        except Exception as e:
            Logger.error(f"Installation step failed: {e}")
            return False

    def _show_mnemonic(self):
        """Display the mnemonic phrase with enhanced security warnings"""
        Logger.section("Wallet Credentials")
        
        mnemonic = self.node_manager.get_cosmos_mnemonic()
        if not mnemonic:
            Logger.error("Could not retrieve mnemonic phrase")
            Logger.info("You may need to check the node configuration manually")
            return

        # Security warnings
        Logger.highlight("CRITICAL SECURITY INFORMATION")
        print(f"{Colors.RED}{Colors.BOLD}This mnemonic phrase is the ONLY way to recover your wallet!{Colors.END}")
        print(f"{Colors.RED}• Store it in a secure location{Colors.END}")
        print(f"{Colors.RED}• Never share it with anyone{Colors.END}")
        print(f"{Colors.RED}• Write it down on paper (recommended){Colors.END}")
        print(f"{Colors.RED}• Do not store it digitally unless encrypted{Colors.END}\n")

        # Display mnemonic
        Logger.highlight("YOUR WALLET MNEMONIC PHRASE")
        print(f"{Colors.BG_YELLOW}{Colors.RED}{Colors.BOLD} {mnemonic} {Colors.END}\n")

        # Confirmation
        while True:
            confirmed = Logger.prompt("Have you safely stored this mnemonic phrase? (yes/no): ")
            if confirmed.lower() in ['yes', 'y']:
                Logger.success("Mnemonic phrase confirmed as stored")
                break
            elif confirmed.lower() in ['no', 'n']:
                Logger.warning("Please store the mnemonic phrase before continuing")
                continue
            else:
                Logger.error("Please answer 'yes' or 'no'")

    def _guide_wallet_setup(self):
        """Guide user through wallet setup and check balance"""
        Logger.section("Wallet Setup and Funding")
        
        Logger.info("Next steps for wallet setup:")
        print(f"  {Colors.CYAN}1.{Colors.END} Download Nym Wallet: {Colors.GREEN_LIGHT}https://nym.com/wallet{Colors.END}")
        print(f"  {Colors.CYAN}2.{Colors.END} Install and open the wallet application")
        print(f"  {Colors.CYAN}3.{Colors.END} Choose 'Restore from mnemonic'")
        print(f"  {Colors.CYAN}4.{Colors.END} Enter the 24-word phrase you saved")
        print(f"  {Colors.CYAN}5.{Colors.END} Fund your wallet with at least {Colors.YELLOW}101 NYM{Colors.END} (100 for bonding, 1 for fees)")
        
        Logger.warning("Minimum 100 NYM required for node bonding!")
        Logger.info("You can purchase NYM on exchanges like:")
        print(f"  • Osmosis.zone, Kraken, Gate.io, etc.")
        print(f"  • Always verify the official contract address")
        
        print(f"\n{Colors.YELLOW}Once your wallet is funded, we need to check the balance.{Colors.END}")

        wallet_address = ""
        while not wallet_address:
            wallet_address = Logger.prompt("Please enter your Nym wallet address (it starts with 'n'): ").strip()
            if not wallet_address.startswith('n'):
                Logger.error("Invalid address format. It should start with 'n'.")
                wallet_address = ""

        while True:
            balance_data = self.node_manager.check_balance(wallet_address)
            
            if balance_data:
                balance_unym = 0
                for coin in balance_data.get('balances', []):
                    if coin.get('denom') == 'unym':
                        balance_unym = int(coin.get('amount', 0))
                        break
                
                balance_nym = balance_unym / 1_000_000

                if balance_nym >= 101:
                    Logger.success(f"Sufficient balance detected: {balance_nym:.6f} NYM")
                    break
                else:
                    Logger.warning(f"Balance is {balance_nym:.6f} NYM. Need at least 101 NYM.")
            else:
                Logger.error("Could not retrieve balance.")

            retry = Logger.prompt("Check balance again? (y/N): ").strip().lower()
            if retry not in ['y', 'yes']:
                Logger.error("Cannot proceed without sufficient funds for bonding.")
                Logger.info("Please fund your wallet and run the script again.")
                sys.exit(1)

        input(f"{Colors.CYAN}Press Enter to proceed to the bonding step...{Colors.END}")

    def _show_completion(self):
        """Show completion message and next steps"""
        Logger.section("Installation Complete!")
        
        Logger.success("Your Nym node has been successfully installed and configured!")
        
        print(f"\n{Colors.BOLD}What's been set up:{Colors.END}")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Nym node binary installed")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Node initialized with ID: {Colors.YELLOW}{self.node_manager.config.node_id}{Colors.END}")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Firewall configured (ports 8080, 1789, 1790, 9000)")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} System service created and started")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Wallet mnemonic generated")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Contract message signed")

        print(f"\n{Colors.BOLD}Useful commands:{Colors.END}")
        print(f"  Check service status: {Colors.CYAN}sudo systemctl status nym-node{Colors.END}")
        print(f"  View logs: {Colors.CYAN}sudo journalctl -u nym-node -f{Colors.END}")
        print(f"  Restart service: {Colors.CYAN}sudo systemctl restart nym-node{Colors.END}")
        
        print(f"\n{Colors.BOLD}Resources:{Colors.END}")
        print(f"  Documentation: {Colors.GREEN_LIGHT}https://nymtech.net/docs{Colors.END}")
        print(f"  Community: {Colors.GREEN_LIGHT}https://discord.gg/nym{Colors.END}")
        print(f"  Status page: {Colors.GREEN_LIGHT}https://status.nymtech.net{Colors.END}")

        Logger.highlight("Your Nym node is now running and ready!")
        Logger.info("Remember to complete the bonding process in the Nym Wallet")

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Nym Node Installer - Enhanced Version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 nym_installer.py                 # Full installation
  python3 nym_installer.py --no-update     # Skip system update
  
This installer will guide you through setting up a Nym mixnode
with enhanced user experience and detailed feedback.
        """
    )
    
    parser.add_argument(
        "--no-update", 
        action="store_true", 
        help="Skip system package update (faster, but not recommended)"
    )
    
    parser.add_argument(
        "--version", 
        action="version", 
        version="Nym Node Installer v2.0 (Enhanced)"
    )
    
    args = parser.parse_args()

    # Check if running on supported system
    if sys.platform != "linux":
        Logger.error("This installer is designed for Linux systems only")
        sys.exit(1)

    # Check Python version
    if sys.version_info < (3, 6):
        Logger.error("Python 3.6 or higher is required")
        sys.exit(1)

    try:
        installer = NymNodeInstaller()
        installer.run(no_update=args.no_update)
    except Exception as e:
        Logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
