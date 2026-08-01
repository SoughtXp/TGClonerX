import os
import sys
import subprocess

def build():
    """
    Compiles TGClonerX into a standalone Windows desktop executable with custom icon.ico.
    """
    print("Compiling TGClonerX standalone Windows executable with custom icon...")
    
    python_exe = sys.executable
    cmd = [
        python_exe, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=TGClonerX",
        "--icon=icon.ico",
        "--add-data=src/templates;src/templates",
        "--add-data=src/static;src/static",
        "--add-data=icon.ico;.",
        "main.py"
    ]
    
    subprocess.run(cmd, check=True)
    print("\n[SUCCESS] TGClonerX.exe successfully compiled into: dist/TGClonerX/TGClonerX.exe")

if __name__ == '__main__':
    build()
