#!/usr/bin/env python3
"""
Nym Node Installer - Automated installation and configuration of a Nym Node
Refactored version
"""

import os
import pwd
import sys
import json
import time
import argparse
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Optional, Dict, Any
import threading
import shutil
import getpass

# ========== Configuration Classes ==========
# @dataclass
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
    GREEN_BRIGHT = '\033[92m'
    GREEN_LIGHT = '\033[38;5;42m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    HIGHLIGHT_BG = '\033[48;5;22m'
    HIGHLIGHT_FG = '\033[38;5;154m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    BG_DARK_RED = '\033[48;5;124m'
    BG_YELLOW = '\033[103m'
    BG_GREEN_BRIGHT = '\033[102m'


# ========== Utility Classes ==========
class ProgressIndicator:
    """Progress indicator for long-running operations"""
    def __init__(self, message: str, spinner_chars: str = '|/-\"'):
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
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self, success_msg: str = None):
        self.running = False
        if self.thread:
            self.thread.join()
        print('\r' + ' ' * (len(self.message) + 10) + '\r', end='', flush=True)
        if success_msg:
            Logger.success(success_msg)
            
    def _spin(self):
        idx = 0
        while self.running:
            char = self.spinner_chars[idx % len(self.spinner_chars)]
            print(f'\r{Colors.GREEN_LIGHT}{char} {self.message}...{Colors.END}', end='', flush=True)
            time.sleep(0.1)
            idx += 1


class Logger:
    """Enhanced logging utilities"""
    @staticmethod
    def success(message: str) -> None:
        print(f"{Colors.GREEN_BRIGHT}{Colors.BOLD}SUCCESS:{Colors.END} {Colors.GREEN_LIGHT}{message}{Colors.END}")

    @staticmethod
    def error(message: str) -> None:
        print(f"{Colors.RED}{Colors.BOLD}ERROR:{Colors.END} {Colors.RED}{message}{Colors.END}")

    @staticmethod
    def warning(message: str) -> None:
        print(f"{Colors.YELLOW}{Colors.BOLD}WARNING:{Colors.END} {Colors.YELLOW}{message}{Colors.END}")

    @staticmethod
    def info(message: str) -> None:
        print(f"{Colors.GREEN_LIGHT}{Colors.BOLD}INFO:{Colors.END} {Colors.GREEN_LIGHT}{message}{Colors.END}")

    @staticmethod
    def debug(message: str) -> None:
        print(f"{Colors.DIM}DEBUG: {message}{Colors.END}")

    @staticmethod
    def step(step_num: int, total_steps: int, message: str) -> None:
        progress = "█" * (step_num * 20 // total_steps) + "░" * (20 - (step_num * 20 // total_steps))
        print(f"{Colors.GREEN_BRIGHT}{Colors.BOLD}[{step_num}/{total_steps}]{Colors.END} "
              f"{Colors.GREEN_LIGHT}[{progress}]{Colors.END} {message}")

    @staticmethod
    def section(title: str) -> None:
        border = "═" * (len(title) + 4)
        print(f"\n{Colors.BOLD}{Colors.GREEN_BRIGHT}{border}")
        print(f"  {title}")
        print(f"{border}{Colors.END}\n")

    @staticmethod
    def highlight(message: str) -> None:
        print(f"{Colors.HIGHLIGHT_BG}{Colors.HIGHLIGHT_FG}{Colors.BOLD} {message} {Colors.END}")

    @staticmethod
    def prompt(message: str) -> str:
        return input(f"{Colors.YELLOW}{Colors.BOLD}{message}{Colors.END} ")

    @staticmethod
    def sudo_prompt(reason: str) -> None:
        print(f"\n{Colors.BG_DARK_RED}{Colors.WHITE}{Colors.BOLD} SUDO REQUIRED {Colors.END}")
        print(f"{Colors.RED}Reason: {reason}{Colors.END}")
        print(f"{Colors.YELLOW}Please enter your password when prompted.{Colors.END}\n")


class CommandRunner:
    """Enhanced command execution utilities"""
    @staticmethod
    def check_sudo_available() -> bool:
        return shutil.which('sudo') is not None

    @staticmethod
    def run(cmd: List[str], sudo: bool = False, capture_output: bool = False,
            text: bool = True, check: bool = False, sudo_reason: str = "") -> subprocess.CompletedProcess:
        if sudo and CommandRunner.check_sudo_available():
            if sudo_reason:
                Logger.sudo_prompt(sudo_reason)
            cmd = ['sudo'] + cmd
        
        try:
            return subprocess.run(cmd, capture_output=capture_output, text=text, check=check)
        except FileNotFoundError:
            Logger.error(f"Command not found: {cmd[0] if cmd else 'unknown'}")
            raise

    @staticmethod
    def run_with_progress(cmd: List[str], progress_msg: str, sudo: bool = False, 
                         sudo_reason: str = "") -> int:
        if sudo and CommandRunner.check_sudo_available():
            if sudo_reason:
                Logger.sudo_prompt(sudo_reason)
            cmd = ['sudo'] + cmd

        try:
            with ProgressIndicator(progress_msg):
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return process.wait()
        except FileNotFoundError:
            Logger.error(f"Command not found: {cmd[0] if cmd else 'unknown'}")
            return 1

    @staticmethod
    def run_with_inline_output(cmd: List[str], sudo: bool = False, sudo_reason: str = "") -> int:
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
                    print(f'\n{Colors.GREEN_LIGHT} {line.strip()[:80]}...{Colors.END}', end='', flush=True)
                    
            process.wait()
            print('\r' + ' ' * 90 + '\r', end='', flush=True)
            return process.returncode
            
        except FileNotFoundError:
            Logger.error(f"Command not found: {cmd[0] if cmd else 'unknown'}")
            return 1


# ========== System Management ==========
class SystemManager:
    """System management utilities"""
    @staticmethod
    def update_system() -> bool:
        Logger.section("Updating System Packages")
        try:
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
            return True
            
        except Exception as e:
            Logger.error(f"System update failed: {e}")
            return False

    @staticmethod
    def install_packages(packages: List[str]) -> bool:
        Logger.section(f"Installing Required Packages")
        if not packages:
            return True

        try:
            result = CommandRunner.run(['dpkg-query', '-W', '-f=${Package}\n'], capture_output=True)
            installed = set(result.stdout.splitlines()) if result.returncode == 0 else set()
            
            to_install = [pkg for pkg in packages if pkg not in installed]
            already_installed = [pkg for pkg in packages if pkg in installed]

            if already_installed:
                Logger.success(f"Already installed: {', '.join(already_installed)}")
            if not to_install:
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
            return False
                
        except Exception as e:
            Logger.error(f"Package installation error: {e}")
            return False


# ========== Network Management ==========
class NetworkManager:
    """Network management utilities"""
    @staticmethod
    def get_public_ip() -> Optional[str]:
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
                    if ip and len(ip.split('.')) == 4:
                        Logger.success(f"Public IP detected: {Colors.YELLOW}{ip}{Colors.END}")
                        return ip
            except Exception:
                continue
                
        Logger.error("Failed to detect public IP address")
        return None

    @staticmethod
    def open_ports(ports: List[int]) -> bool:
        Logger.section(f"Configuring Firewall")
        
        if not shutil.which('ufw'):
            Logger.info("ufw not found, installing...")
            if not SystemManager.install_packages(['ufw']):
                return False

        try:
            result = CommandRunner.run(['ufw', 'status'], capture_output=True)
            if "inactive" in result.stdout.lower():
                Logger.info("Enabling firewall...")
                result = CommandRunner.run(['ufw', '--force', 'enable'], sudo=True)
                if result.returncode != 0:
                    return False
                Logger.success("Firewall enabled")

            success_count = 0
            for i, port in enumerate(ports, 1):
                Logger.step(i, len(ports), f"Opening port {port}")
                result = CommandRunner.run(['ufw', 'allow', str(port)], sudo=True)
                if result.returncode == 0:
                    success_count += 1
                    Logger.success(f"Port {port} opened successfully")
                else:
                    Logger.error(f"Failed to open port {port}")

            if success_count == len(ports):
                Logger.success(f"All {len(ports)} ports configured successfully")
                return True
            Logger.warning(f"Only {success_count}/{len(ports)} ports were configured")
            return False

        except Exception as e:
            Logger.error(f"Firewall configuration error: {e}")
            return False


# ========== Nym Node Management ==========
class NymNodeManager:
    """Nym Node management core"""
    def __init__(self):
        self.config = NodeConfig()
        self.dest_dir = Path.home() / "nym"
        self.dest_dir.mkdir(exist_ok=True)

    def check_if_node_installed(self) -> bool:
        nym_dir = Path.home() / ".nym"
        binary_exists = Path("/usr/local/bin/nym-node").exists()
        return nym_dir.exists() or binary_exists

    def download_latest_binary(self) -> str:
        Logger.section("Downloading Nym Node Binary")
        api_url = "https://api.github.com/repos/nymtech/nym/releases/latest"
        
        try:
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
            Logger.error("Could not find nym-node binary")
            return ""

        tmp_path = "/tmp/nym-node"
        binary_dest_path = "/usr/local/bin/nym-node"
        
        try:
            with ProgressIndicator("Downloading nym-node binary"):
                urllib.request.urlretrieve(download_url, tmp_path)
            
            CommandRunner.run(['mv', tmp_path, binary_dest_path], sudo=True)
            CommandRunner.run(['chmod', '+x', binary_dest_path], sudo=True)
            
            Logger.success(f"Binary installed: {Colors.YELLOW}{binary_dest_path}{Colors.END}")
            self.config.binary_path = binary_dest_path
            return binary_dest_path
            
        except Exception as e:
            Logger.error(f"Binary installation failed: {e}")
            return ""

    def initialize_node(self) -> bool:
        Logger.section("Node Initialization")
        while not self.config.node_id:
            self.config.node_id = Logger.prompt("Enter your unique node ID: ").strip()
            if not self.config.node_id:
                Logger.error("Node ID cannot be empty!")
            elif len(self.config.node_id) < 3:
                Logger.error("Node ID must be at least 3 characters long!")
                self.config.node_id = ""

        self.config.public_ip = NetworkManager.get_public_ip()
        if not self.config.public_ip:
            manual_ip = Logger.prompt("Could not detect IP. Enter manually (or press Enter to retry): ")
            if manual_ip.strip():
                self.config.public_ip = manual_ip.strip()
            else:
                return False

        try:
            with ProgressIndicator("Initializing node configuration"):
                subprocess.run([
                    self.config.binary_path, "run", "--mode", "mixnode",
                    "--id", self.config.node_id, "--init-only",
                    "--public-ips", self.config.public_ip,
                    "--accept-operator-terms-and-conditions"
                ], capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            Logger.error(f"Node initialization failed: {e.stderr if e.stderr else e}")
            return False

    def create_description_toml(self) -> str:
        base_dir = Path.home() / ".nym" / "nym-nodes" / self.config.node_id / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        file_path = base_dir / "description.toml"

        Logger.info("Configure your node description (optional):")
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
            return str(file_path)
        except Exception as e:
            Logger.error(f"Failed to create description file: {e}")
            return ""

    def create_systemd_service(self) -> bool:
        if not self.config.node_id:
            return False

        service_name = "nym-node.service"
        service_path = f"/etc/systemd/system/{service_name}"
        current_user = subprocess.run(['whoami'], capture_output=True, text=True, check=True).stdout.strip()
        try:
            home_dir = pwd.getpwnam(current_user).pw_dir
        except KeyError:
            home_dir = f"/home/{current_user}" if current_user != "root" else "/root"        

        service_content = f"""
[Unit]
Description=Nym Node ({self.config.node_id})
After=network.target
Wants=network.target

[Service]
Type=simple
User={current_user}
WorkingDirectory={home_dir}
ExecStart={self.config.binary_path} run --mode mixnode --id {self.config.node_id} --accept-operator-terms-and-conditions
Restart=always
RestartSec=10
LimitNOFILE=65535

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=false
ReadWritePaths={home_dir}/.nym

[Install]
WantedBy=multi-user.target
"""

        try:
            tmp_service = "/tmp/nym-node.service"
            with open(tmp_service, "w") as f:
                f.write(service_content)

            CommandRunner.run(['mv', tmp_service, service_path], sudo=True)
            CommandRunner.run(['chmod', '644', service_path], sudo=True)
            CommandRunner.run(['systemctl', 'daemon-reload'], sudo=True)
            CommandRunner.run(['systemctl', 'enable', service_name], sudo=True)
            CommandRunner.run(['systemctl', 'start', service_name], sudo=True)
            return True
        except Exception as e:
            Logger.error(f"Service setup failed: {e}")
            return False

    def get_bonding_information(self) -> Dict[str, str]:
        try:
            result = subprocess.run([
                self.config.binary_path, "bonding-information", "--id", self.config.node_id
            ], capture_output=True, check=True, text=True, timeout=30)

            bonding_info = {}
            for line in result.stdout.strip().split('\n'):
                if "Identity Key:" in line:
                    bonding_info["identity_key"] = line.split(":", 1)[1].strip()
                elif "Host:" in line:
                    bonding_info["host"] = line.split(":", 1)[1].strip()
            
            if not bonding_info.get("host"):
                bonding_info["host"] = self.config.public_ip
            return bonding_info
        except Exception as e:
            Logger.error(f"Failed to get bonding information: {e}")
            return {}

    def get_cosmos_mnemonic(self) -> str:
        mnemonic_path = Path.home() / ".nym" / "nym-nodes" / self.config.node_id / "data" / "cosmos_mnemonic"
        if not mnemonic_path.exists():
            Logger.error("Cosmos mnemonic file not found")
            return ""

        try:
            with open(mnemonic_path, 'r') as f:
                mnemonic = f.read().strip()
            self.config.cosmos_mnemonic = mnemonic
            return mnemonic
        except Exception as e:
            Logger.error(f"Error reading cosmos mnemonic: {e}")
            return ""

    @staticmethod
    def check_balance(address: str) -> Optional[float]:
        """Check NYX account balance using direct LCD endpoint"""
        Logger.info(f"Checking account balance for: {Colors.YELLOW}{address}{Colors.END}")
        
        try:
            api_url = f"https://api.nymtech.net/cosmos/bank/v1beta1/balances/{address}"
            
            with urllib.request.urlopen(api_url, timeout=15) as response:
                data = json.loads(response.read().decode())
            balance_unym = 0
            for balance in data.get("balances", []):
                if balance.get("denom") == "unym":
                    try:
                        balance_unym = int(balance.get("amount", "0"))
                        break
                    except ValueError:
                        Logger.error("Invalid amount format in balance response")
                        return None
            balance_nym = balance_unym / 1_000_000
            
            if balance_nym >= 101:
                Logger.success(f"Current balance: {Colors.GREEN_BRIGHT}{balance_nym:.6f} NYM{Colors.END}")
            elif balance_nym > 0:
                Logger.warning(f"Current balance: {Colors.YELLOW}{balance_nym:.6f} NYM{Colors.END} (need 101 NYM)")
            else:
                Logger.error(f"Current balance: {Colors.RED}0 NYM{Colors.END} (need ≥101 NYM)")
            
            return balance_nym
        except urllib.error.HTTPError as e:
            Logger.error(f"API request failed with status {e.code}: {e.reason}")
            return None
        except json.JSONDecodeError:
            Logger.error("Failed to parse API response")
            return None
        except Exception as e:
            Logger.error(f"Failed to check balance: {e}")
            return None

    def sign_contract_message(self) -> None:
        Logger.section("Contract Message Signing")
        bonding_info = self.get_bonding_information()
        if not bonding_info:
            Logger.error("Cannot proceed without bonding information")
            return

        Logger.highlight("BONDING INFORMATION FOR WALLET")
        print(f"{Colors.BOLD}Identity Key:{Colors.END} {Colors.YELLOW}{bonding_info['identity_key']}{Colors.END}")
        print(f"{Colors.BOLD}Host:{Colors.END} {Colors.YELLOW}{bonding_info['host']}{Colors.END}")
        
        Logger.info("\nInstructions (https://nym.com/docs/operators/nodes/nym-node/bonding#3-enter-your-values-and-sign-with-your-node):")
        Logger.info("1. Open the Nym Wallet application")
        Logger.info("2. Go to the bonding section")
        Logger.info("3. Use the information above to generate the payload")
        Logger.info("4. Copy the generated payload and paste it below")
        
        while True:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}Please paste the payload generated by the wallet:{Colors.END}")
            payload = input(f"{Colors.CYAN}> {Colors.END}").strip()
            if payload and len(payload) >= 10:
                break
            Logger.error("Invalid payload. Please try again.")

        try:
            cmd = [self.config.binary_path, "sign", "--id", self.config.node_id, "--contract-msg", payload]
            with ProgressIndicator("Processing signature"):
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            signature = self._extract_signature(result.stdout)
            if signature:
                Logger.success("Contract message signed successfully!")
                Logger.highlight("ENTER THIS SIGNATURE IN YOUR WALLET")
                print(f"\n{Colors.BG_GREEN_BRIGHT}{Colors.BOLD} {signature} {Colors.END}\n")
                
                while True:
                    confirmed = Logger.prompt("Have you copied the signature to your wallet? (yes/no): ")
                    if confirmed.lower() in ['yes', 'y']:
                        Logger.success("Signature confirmed as copied")
                        return
            else:
                Logger.highlight("FULL SIGNATURE OUTPUT")
                print(f"{Colors.GREEN_LIGHT}{result.stdout}{Colors.END}")

                print(f"{Colors.BOLD}{Colors.GREEN_LIGHT} PASTED SIGNATURE INTO WALLET:{Colors.END}")
                print(f"{Colors.GREEN_LIGHT}{signature}{Colors.END}")
        except subprocess.CalledProcessError as e:
            Logger.error(f"Signing failed: {e.stderr if e.stderr else e}")

    def _extract_signature(self, output: str) -> Optional[str]:
        try:
            # Сначала пробуем найти по разделителю "is:\n"
            if "is:\n" in output:
                return output.split("is:\n")[-1].strip()
            
            # Если не сработало, ищем в последней строке
            last_line = output.strip().split('\n')[-1].strip()
            if last_line and len(last_line) > 40:
                return last_line
            
            # Пробуем найти через разделитель "is:"
            for line in output.split('\n'):
                if 'is:' in line:
                    return line.split('is:', 1)[-1].strip()
            
            return None
        except Exception as e:
            Logger.error(f"Error extracting signature: {e}")
            return None


# ========== Main Installer ==========
class NymNodeInstaller:
    """Main installer class"""
    def __init__(self):
        self.node_manager = NymNodeManager()

    def run(self, no_update: bool = False):
        try:
            self._print_welcome()
            if not self._install_node(no_update=no_update):
                sys.exit(1)
            self._show_mnemonic()
            self._guide_wallet_setup()
            self.node_manager.sign_contract_message()
            self._show_completion()
        except KeyboardInterrupt:
            Logger.warning("\nInstallation interrupted")
            sys.exit(1)
        except Exception as e:
            Logger.error(f"Unexpected error: {e}")
            sys.exit(1)

    def _print_welcome(self):
        border = "─" * 40
        print(f"\n{Colors.BOLD}{Colors.GREEN_BRIGHT}{border}")
        print(f"    Welcome to the Nym Node Installer!")
        print(f"         Enhanced & User-Friendly")
        print(f"{border}{Colors.END}\n")
        
        Logger.info("This installer will:")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Update your system (optional)")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Install required dependencies")
        print(f"  {Colors.GREEN_BRIGHT}•{Colors.END} Configure Nym node")
        
        if not Logger.prompt("Continue? (y/N): ").lower().startswith('y'):
            Logger.info("Installation cancelled")
            sys.exit(0)

    def _install_node(self, no_update: bool = False) -> bool:
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
            
            # System Update
            if not no_update:
                step_num += 1
                Logger.step(step_num, len(active_steps), "Updating system packages")
                if not SystemManager.update_system():
                    return False

            # Install dependencies
            step_num += 1
            Logger.step(step_num, len(active_steps), "Installing dependencies")
            if not SystemManager.install_packages(['curl', 'wget']):
                return False

            # Check for existing installation
            if self.node_manager.check_if_node_installed():
                Logger.warning("Existing Nym node detected")
                reinstall = Logger.prompt("Reinstall? This will overwrite configuration (y/N): ")
                if not reinstall.lower().startswith('y'):
                    return False

            # Download binary
            step_num += 1
            Logger.step(step_num, len(active_steps), "Downloading Nym node binary")
            if not self.node_manager.download_latest_binary():
                return False

            # Configure firewall
            step_num += 1
            Logger.step(step_num, len(active_steps), "Configuring firewall")
            if not NetworkManager.open_ports([8080, 1789, 1790, 9000]):
                Logger.warning("Firewall configuration had issues, continuing...")

            # Initialize node
            step_num += 1
            Logger.step(step_num, len(active_steps), "Initializing node")
            if not self.node_manager.initialize_node():
                return False
            self.node_manager.create_description_toml()

            # Setup service
            step_num += 1
            Logger.step(step_num, len(active_steps), "Setting up system service")
            if not self.node_manager.create_systemd_service():
                return False

            return True
        except Exception as e:
            Logger.error(f"Installation step failed: {e}")
            return False

    def _show_mnemonic(self):
        Logger.section("Wallet Credentials")
        mnemonic = self.node_manager.get_cosmos_mnemonic()
        if not mnemonic:
            return

        Logger.highlight("CRITICAL SECURITY INFORMATION")
        print(f"{Colors.RED}{Colors.BOLD}This mnemonic is the ONLY way to recover your wallet!{Colors.END}")
        print(f"{Colors.RED}• Store it securely{Colors.END}")
        print(f"{Colors.RED}• Never share it{Colors.END}")
        print(f"{Colors.RED}• Write it down on paper{Colors.END}\n")

        Logger.highlight("YOUR WALLET MNEMONIC PHRASE")
        print(f"{Colors.BG_YELLOW}{Colors.RED}{Colors.BOLD} {mnemonic} {Colors.END}\n")

        while True:
            confirmed = Logger.prompt("Have you safely stored this mnemonic? (yes/no): ")
            if confirmed.lower() in ['yes', 'y']:
                break

    def _guide_wallet_setup(self):
        Logger.section("Wallet Setup and Funding")
        
        Logger.info("Next steps:")
        print(f"  {Colors.CYAN}1.{Colors.END} Download Nym Wallet: {Colors.GREEN_LIGHT}https://nym.com/wallet{Colors.END}")
        print(f"  {Colors.CYAN}2.{Colors.END} Install and open wallet")
        print(f"  {Colors.CYAN}3.{Colors.END} Choose 'Restore from mnemonic'")
        print(f"  {Colors.CYAN}4.{Colors.END} Enter your 24-word phrase")
        print(f"  {Colors.CYAN}5.{Colors.END} Fund with {Colors.YELLOW}101+ NYM{Colors.END}")
        
        print(f"\n{Colors.YELLOW}Once funded, enter your wallet address:{Colors.END}")

        wallet_address = ""
        while not wallet_address:
            wallet_address = Logger.prompt("Enter your Nym wallet address (starts with 'n'): ").strip()
            if not wallet_address.startswith('n'):
                Logger.error("Invalid address format")
                wallet_address = ""

        while True:
            balance_nym = self.node_manager.check_balance(wallet_address)
            
            if balance_nym is not None:
                if balance_nym >= 101:
                    Logger.success("Sufficient balance detected!")
                    break
                Logger.warning(f"Insufficient balance: {balance_nym:.6f} NYM. Need 101 NYM.")
                Logger.info("If you just sent funds, wait a few minutes")
            else:
                Logger.error("Could not retrieve balance")

            retry = Logger.prompt("Check balance again? (y/N): ").strip().lower()
            if retry not in ['y', 'yes']:
                Logger.error("Cannot proceed without sufficient funds")
                sys.exit(1)
                
            Logger.info("Waiting 10 seconds...")
            time.sleep(10)

        input(f"{Colors.CYAN}Press Enter to proceed to bonding...{Colors.END}")

    def _show_completion(self):
        Logger.section("Installation Complete!")
        Logger.success("Your Nym node is successfully installed!")
        
        print(f"\n{Colors.BOLD}What's set up:{Colors.END}")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Nym node binary")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Node ID (Moniker): {Colors.YELLOW}{self.node_manager.config.node_id}{Colors.END}")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Firewall configured")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} System service")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Wallet mnemonic")
        print(f"  {Colors.GREEN_BRIGHT}✓{Colors.END} Contract message signed")

        print(f"\n{Colors.BOLD}Commands:{Colors.END}")
        print(f"  Check status: {Colors.CYAN}sudo systemctl status nym-node{Colors.END}")
        print(f"  View logs: {Colors.CYAN}sudo journalctl -u nym-node -f{Colors.END}")
        
        Logger.highlight("Your Nym node is now running!")
        Logger.info("Complete bonding in Nym Wallet")
        Logger.info("---------------------------------")
        Logger.info("wait for the next epoch and check:")
        Logger.info(f"https://nymesis.vercel.app/?q={self.node_manager.config.node_id}")
        Logger.info("---------------------------------")
        Logger.info("Delegate to my node:")
        Logger.info("G2adZrt5ByjSZKrR6G139FYfd4ScxHbinQjpP28h4APm")
        Logger.info("E3BayLcp2RiQ66ZxzkPkZuREYCYrsHB1o7vFULQ6u6Np")
        Logger.info("F618gw6jZaLR1VdMTeaH11MhHQJY5rdpYEDLrMKEHcjk")
        Logger.info("if you want to thank me here's the NYM wallet: n18lc3qmx4jqzr55gvh5qmg6z3q4874x4xmmhhqd")


def main():
    parser = argparse.ArgumentParser(
        description="Nym Node Installer - Enhanced Version",
        epilog="Examples:\n  python3 nym_installer.py\n  python3 nym_installer.py --no-update"
    )
    parser.add_argument("--no-update", action="store_true", help="Skip system update")
    parser.add_argument("--version", action="version", version="Nym Node Installer v2.0")
    args = parser.parse_args()

    if sys.platform != "linux":
        Logger.error("Linux only")
        sys.exit(1)

    if sys.version_info < (3, 6):
        Logger.error("Python 3.6+ required")
        sys.exit(1)

    try:
        NymNodeInstaller().run(no_update=args.no_update)
    except Exception as e:
        Logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()