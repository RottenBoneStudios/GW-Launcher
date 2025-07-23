// editor.js
const { ipcRenderer } = require('electron');
const fs = require('fs');
const path = require('path');
const os = require('os');

const profilesFile = path.join(os.homedir(), '.gwlauncher', 'ui_profiles.json');

const recommendedFlagsMap = {
    8: [
        "-XX:+UseG1GC",
        "-XX:G1NewSizePercent=30",
        "-XX:G1MaxNewSizePercent=40",
        "-XX:G1HeapRegionSize=16M",
        "-XX:G1ReservePercent=20",
        "-XX:MaxGCPauseMillis=50",
        "-XX:G1HeapWastePercent=5",
        "-XX:G1MixedGCCountTarget=4",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+PerfDisableSharedMem",
        "-XX:+AlwaysPreTouch"
    ],
    17: [
        "-XX:+UseZGC",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+DisableExplicitGC",
        "-XX:+AlwaysPreTouch"
    ],
    21: [
        "--enable-preview",
        "-XX:+UseZGC",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+DisableExplicitGC",
        "-XX:+AlwaysPreTouch"
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

function getRecommendedFlags(mcVersion) {
    const select = document.getElementById('version');
    const selected = select.selectedOptions[0];
    const modloader = selected?.dataset?.modloader || 'vanilla';

    if (modloader === 'fabric' || modloader === 'forge' || modloader === 'quilt') {
        return [];
    }

    const javaVer = getJavaVersion(mcVersion);
    return recommendedFlagsMap[javaVer] || [];
}

function arraysEqual(a, b) {
    return a.length === b.length && a.every((val, i) => val === b[i]);
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

function parseRamInput(value) {
    const trimmed = value.trim().toLowerCase();
    if (/^\d+g$/.test(trimmed)) {
        return parseInt(trimmed) * 1024;
    }
    return parseInt(trimmed) || 2048;
}

function loadVersions() {
    const versionSelect = document.getElementById('version');
    versionSelect.innerHTML = '<option value="" disabled selected>Selecciona una versión</option>';

    const dir = path.join(os.homedir(), '.gwlauncher');
    const sources = {
        vanilla: path.join(dir, 'versiones-minecraft.json'),
        fabric: path.join(dir, 'versiones-fabric.json'),
        forge: path.join(dir, 'versiones-forge.json'),
        quilt: path.join(dir, 'versiones-quilt.json')
    };

    const versionsMap = new Map();

    for (const [modloader, filePath] of Object.entries(sources)) {
        if (!fs.existsSync(filePath)) continue;

        try {
            const rawData = fs.readFileSync(filePath, 'utf8');
            const data = JSON.parse(rawData);
            let versions = [];

            if (modloader === 'forge') {
                const grouped = {};
                for (const ver of data) {
                    const mcVer = ver.split(/[-_]/)[0];
                    if (!grouped[mcVer]) grouped[mcVer] = [];
                    grouped[mcVer].push(ver);
                }
                for (const mcVer in grouped) {
                    versions.push({ version: mcVer, modloader });
                }
            } else {
                const list = Array.isArray(data) ? data : data.versions || [];
                const filtered = modloader === 'vanilla'
                    ? list.filter(v => v.type === 'release')
                    : list.filter(v => typeof v === 'string' || v.stable === true);

                for (const entry of filtered) {
                    const ver = typeof entry === 'string' ? entry : entry.version || entry.id;
                    if (ver) versions.push({ version: ver, modloader });
                }
            }

            for (const { version, modloader } of versions) {
                const key = `${version}|${modloader}`;
                versionsMap.set(key, { version, modloader });
            }
        } catch (e) {
            console.warn(`[ERROR] Al leer ${filePath}:`, e);
        }
    }

    const finalList = Array.from(versionsMap.values())
        .sort((a, b) => b.version.localeCompare(a.version, undefined, { numeric: true }));

    for (const { version, modloader } of finalList) {
        const opt = document.createElement('option');
        opt.value = version;
        opt.dataset.modloader = modloader;
        opt.textContent = modloader === 'vanilla' ? version : `${version} (${modloader})`;
        versionSelect.appendChild(opt);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadVersions();

    const params = new URLSearchParams(location.search);
    const profName = params.get('name');
    const btnOpt = document.getElementById('btn-opt');
    const versionSelect = document.getElementById('version');
    const jvmFlagsInput = document.getElementById('jvm-flags');
    const ramInput = document.getElementById('ram');
    const form = document.getElementById('editor');
    const btnClose = document.getElementById('close-btn');

    if (btnClose) btnClose.addEventListener('click', () => window.close());

    ramInput.value = 2048;
    ramInput.step = 1024;
    ramInput.min = 2048;

    ramInput.addEventListener('input', () => {
        let value = ramInput.value.trim().toLowerCase();

        if (/^\d+g$/.test(value)) {
            ramInput.value = parseInt(value) * 1024;
        } else if (/^\d+$/.test(value)) {
            ramInput.value = parseInt(value);
        } else {
            showWarning('RAM inválida. Usa un número en MiB o formato como "4g".');
            ramInput.value = 2048;
        }
    });

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
                    ramInput.value = profile.ram || 2048;
                    jvmFlagsInput.value = (profile.jvmFlags || []).join(' ');

                    const opts = versionSelect.options;
                    for (const option of opts) {
                        if (
                            option.value === profile.version &&
                            option.dataset.modloader === profile.modloader
                        ) {
                            versionSelect.value = option.value;
                            option.selected = true;
                            break;
                        }
                    }
                }
            } catch (e) {
                console.warn('Error al cargar perfiles:', e);
            }
        }
    }

    versionSelect.addEventListener('change', () => {
        const currentFlags = jvmFlagsInput.value.trim().split(/\s+/).filter(Boolean);
        const newRecommended = getRecommendedFlags(versionSelect.value);
        if (arraysEqual(currentFlags, recommendedFlagsMap[8]) ||
            arraysEqual(currentFlags, recommendedFlagsMap[17]) ||
            arraysEqual(currentFlags, recommendedFlagsMap[21])) {
            jvmFlagsInput.value = newRecommended.join(' ');
        }
    });

    btnOpt.addEventListener('click', () => {
        const mcVersion = versionSelect.value;
        if (!mcVersion) {
            showWarning('Selecciona primero una versión.');
            return;
        }
        const flags = getRecommendedFlags(mcVersion);
        jvmFlagsInput.value = flags.join(' ');
    });

    form.addEventListener('submit', e => {
        e.preventDefault();

        const name = document.getElementById('prof-name').value.trim();
        const ramMiB = parseRamInput(ramInput.value);

        if (ramMiB < 2048) {
            showWarning('La RAM mínima es 2048 MiB');
            return;
        }

        const selectedOption = versionSelect.selectedOptions[0];
        const version = selectedOption?.value || '';
        const modloader = selectedOption?.dataset.modloader || 'vanilla';

        const profiles = fs.existsSync(profilesFile)
            ? JSON.parse(fs.readFileSync(profilesFile, 'utf8'))
            : {};

        profiles[name] = {
            username: document.getElementById('username').value.trim(),
            version,
            modloader,
            ram: ramMiB,
            jvmFlags: jvmFlagsInput.value.trim().split(/\s+/).filter(Boolean)
        };

        fs.mkdirSync(path.dirname(profilesFile), { recursive: true });
        fs.writeFileSync(profilesFile, JSON.stringify(profiles, null, 2));

        ipcRenderer.send('profile-saved', name);
        window.close();
    });
});
