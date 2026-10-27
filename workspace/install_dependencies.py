import subprocess
import sys

def install_pygame():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pygame"])
        print("pygame installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install pygame: {e}")

if __name__ == "__main__":
    print("Attempting to install pygame...")
    install_pygame()
