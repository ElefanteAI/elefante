import os
import sys
import shutil
import subprocess
import logging


# Setup logging to file and console
log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reinstall.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def run_command(command, cwd=None, env=None):
    logger.info(f"Running: {' '.join(command)}")
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=True)
        if result.stdout:
            logger.info(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e.stderr}")
        raise


def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(project_root)

    logger.info(f"Project root: {project_root}")

    # 1. Find Python 3.11
    python_exe = shutil.which("python3.11")
    if not python_exe:
        python_exe = shutil.which("python3")
        if python_exe:
            try:
                ver = subprocess.check_output([python_exe, "--version"]).decode().strip()
                logger.info(f"Found python3 version: {ver}")
                if "3.11" not in ver:
                    logger.warning(f"python3 is {ver}, looking for explicit python3.11")
                    python_exe = None
            except Exception:
                python_exe = None

    if not python_exe:
        python_exe = shutil.which("python")
        if python_exe:
            try:
                ver = subprocess.check_output([python_exe, "--version"]).decode().strip()
                logger.info(f"Found python version: {ver}")
                if "3.11" not in ver:
                    python_exe = None
            except Exception:
                python_exe = None

    if not python_exe:
        logger.error("Python 3.11 not found in PATH. Please install it.")
        sys.exit(1)

    logger.info(f"Using Python executable: {python_exe}")

    # 2. Delete existing .venv
    venv_path = os.path.join(project_root, ".venv")
    if os.path.exists(venv_path):
        logger.info(f"Removing existing venv at {venv_path}")
        subprocess.run(["rm", "-rf", venv_path], check=True)

    # 3. Create new venv
    logger.info("Creating new virtual environment...")
    run_command([python_exe, "-m", "venv", ".venv"])

    # 4. Install dependencies
    pip_exe = os.path.join(venv_path, "bin", "pip")
    if sys.platform == "win32":
        pip_exe = os.path.join(venv_path, "Scripts", "pip.exe")

    logger.info("Installing dependencies...")
    run_command([pip_exe, "install", "--upgrade", "pip"])
    run_command([pip_exe, "install", "-r", "requirements.txt"])

    # 5. Initialize databases
    python_venv_exe = os.path.join(venv_path, "bin", "python")
    if sys.platform == "win32":
        python_venv_exe = os.path.join(venv_path, "Scripts", "python.exe")

    logger.info("Initializing databases...")
    run_command([python_venv_exe, "scripts/init_databases.py"])

    # 6. Run health check
    logger.info("Running health check...")
    run_command([python_venv_exe, "scripts/health_check.py"])

    logger.info("OK: Clean installation complete")


if __name__ == "__main__":
    main()
