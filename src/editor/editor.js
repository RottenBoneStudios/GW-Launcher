/*--   GW Launcher – editor.js   */
const { ipcRenderer } = require('electron');
const fs = require('fs');
const path = require('path');
const os = require('os');

const profilesFile = path.join(os.homedir(), '.gwlauncher', 'ui_profiles.json');
const recommendedFlags = [
    '-XX:+UnlockExperimentalVMOptions',
    '-XX:+UseG1GC',
    '-XX:G1NewSizePercent=30',
    '-XX:G1MaxNewSizePercent=40',
    '-XX:G1HeapRegionSize=16M',
    '-XX:G1ReservePercent=20',
    '-XX:MaxGCPauseMillis=50',
    '-XX:G1HeapWastePercent=5',
    '-XX:G1MixedGCCountTarget=4',
    '-XX:+PerfDisableSharedMem',
    '-XX:+AlwaysPreTouch'
];

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(location.search);
    const profName = params.get('name');
    const btnClose = document.getElementById('close-btn');

    if (btnClose) {
        btnClose.addEventListener('click', () => {
            window.close();
        });
    }

    if (profName) {
        document.getElementById('editor-title').textContent = `Editar perfil: ${profName}`;
        document.getElementById('prof-name').value = profName;
        document.getElementById('prof-name').disabled = true;

        if (fs.existsSync(profilesFile)) {
            try {
                const profiles = JSON.parse(fs.readFileSync(profilesFile, 'utf8'));
                const profile = profiles[profName];
                if (profile) {
                    document.getElementById('username').value = profile.username || '';
                    document.getElementById('version').value = profile.version || '';
                    document.getElementById('modloader').value = profile.modloader || 'vanilla';
                    document.getElementById('ram').value = profile.ram || '';
                    document.getElementById('jvm-flags').value = (profile.jvmFlags || []).join(' ');
                }
            } catch (e) {
                console.warn('Error al cargar perfiles:', e);
            }
        }
    }

    document.getElementById('editor').addEventListener('submit', e => {
        e.preventDefault();
        const name = document.getElementById('prof-name').value.trim();
        const profiles = fs.existsSync(profilesFile)
            ? JSON.parse(fs.readFileSync(profilesFile, 'utf8'))
            : {};

        profiles[name] = {
            username: document.getElementById('username').value.trim(),
            version: document.getElementById('version').value,
            modloader: document.getElementById('modloader').value,
            ram: document.getElementById('ram').value.trim(),
            jvmFlags: document.getElementById('jvm-flags').value
                .trim().split(/\s+/).filter(Boolean)
        };
        fs.mkdirSync(path.dirname(profilesFile), { recursive: true });
        fs.writeFileSync(profilesFile, JSON.stringify(profiles, null, 2));

        ipcRenderer.send('profile-saved', name);
        window.close();
    });


    document.getElementById('btn-opt').addEventListener('click', () => {
        document.getElementById('jvm-flags').value = recommendedFlags.join(' ');
    });
});
