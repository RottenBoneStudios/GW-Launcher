python -m venv gwlauncher_env
gwlauncher_env\Scripts\activate
pip install pyinstaller minecraft-launcher-lib requests PySide6 pypresence
python -m PyInstaller --onefile --windowed --noconfirm --clean --icon="%CD%\assets\icon.ico" --add-data "assets;assets" --name "GWLauncher" gw_launcher.py
