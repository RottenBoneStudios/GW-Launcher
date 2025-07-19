const { ipcRenderer } = require('electron');
const fs = require('fs');
const path = require('path');
const os = require('os');

const profilesFile = path.join(os.homedir(), '.gwlauncher', 'ui_profiles.json');

const recommendedFlagsMap = {
    8: [
        '-XX:+UseG1GC',
        '-XX:G1NewSizePercent=30',
        '-XX:G1MaxNewSizePercent=40',
        '-XX:G1HeapRegionSize=16M',
        '-XX:G1ReservePercent=20',
        '-XX:MaxGCPauseMillis=50',
        '-XX:G1HeapWastePercent=5',
        '-XX:G1MixedGCCountTarget=4',
        '-XX:+UnlockExperimentalVMOptions',
        '-XX:+PerfDisableSharedMem',
        '-XX:+AlwaysPreTouch'
    ],
    17: [
        '-XX:+UseZGC',
        '-XX:+UnlockExperimentalVMOptions',
        '-XX:+DisableExplicitGC',
        '-XX:+AlwaysPreTouch'
    ],
    21: [
        '-XX:+UseZGC',
        '-XX:+UnlockExperimentalVMOptions',
        '-XX:+DisableExplicitGC',
        '-XX:+AlwaysPreTouch'
    ]
};

function getJavaVersion(mcVersion) {
    const parts = mcVersion.split('.').map(Number);
    const [major, minor] = parts;
    if (major === 1) {
        if (minor >= 8 && minor <= 16) return 8;
        if (minor >= 17 && minor <= 19) return 17;
        if (minor >= 20) return 21;
    }
    return 8;
}

function showWarning(message) {
    if (document.querySelector('.custom-warning')) return;

    const warning = document.createElement('div');
    warning.className = 'custom-warning';
    warning.textContent = message;
    const btnOpt = document.getElementById('btn-opt');
    if (btnOpt && btnOpt.parentNode) {
        btnOpt.parentNode.insertBefore(warning, btnOpt.nextSibling);
    } else {
        document.body.appendChild(warning);
    }
    setTimeout(() => {
        warning.remove();
    }, 3000);
}

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(location.search);
    const profName = params.get('name');
    const btnOpt = document.getElementById('btn-opt');
    const versionSelect = document.getElementById('version');
    const jvmFlagsInput = document.getElementById('jvm-flags');
    const form = document.getElementById('editor');
    const btnClose = document.getElementById('close-btn');

    if (btnClose) btnClose.addEventListener('click', () => window.close());

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
                    versionSelect.value = profile.version || '';
                    document.getElementById('modloader').value = profile.modloader || 'vanilla';
                    document.getElementById('ram').value = profile.ram || '';
                    jvmFlagsInput.value = (profile.jvmFlags || []).join(' ');
                }
            } catch (e) {
                console.warn('Error al cargar perfiles:', e);
            }
        }
    }

    btnOpt.addEventListener('click', () => {
        const mcVersion = versionSelect.value;
        if (!mcVersion) {
            showWarning('Selecciona primero una versión.');
            return;
        }
        const javaVer = getJavaVersion(mcVersion);
        const flags = recommendedFlagsMap[javaVer] || [];
        jvmFlagsInput.value = flags.join(' ');
    });

    form.addEventListener('submit', e => {
        e.preventDefault();
        const name = document.getElementById('prof-name').value.trim();
        const profiles = fs.existsSync(profilesFile)
            ? JSON.parse(fs.readFileSync(profilesFile, 'utf8'))
            : {};

        profiles[name] = {
            username: document.getElementById('username').value.trim(),
            version: versionSelect.value,
            modloader: document.getElementById('modloader').value,
            ram: document.getElementById('ram').value.trim(),
            jvmFlags: jvmFlagsInput.value.trim().split(/\s+/).filter(Boolean)
        };
        fs.mkdirSync(path.dirname(profilesFile), { recursive: true });
        fs.writeFileSync(profilesFile, JSON.stringify(profiles, null, 2));

        ipcRenderer.send('profile-saved', name);
        window.close();
    });
});
