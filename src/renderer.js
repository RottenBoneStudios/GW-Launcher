const { exec } = require('child_process');
const path = require('path');

function launchMinecraft () {
  const username  = document.getElementById('username').value.trim();
  const version   = document.getElementById('version').value.trim();
  const modloader = document.getElementById('modloader').value;
  const ram       = document.getElementById('ram').value.trim();

  if (!username || !version) { alert('Username y versión son obligatorios'); return; }

  //  ➜   C:\Users\Angel\Desktop\GW-Launcher\src\python\gwlauncher_backend.py
  const pythonScript = path.join(__dirname, 'python', 'gwlauncher_backend.py');

  // Construir CLI
  let cmd = `python "${pythonScript}" launch "${version}" "${username}"`;
  if (ram)       cmd += ` --ram ${ram}`;
  if (modloader) cmd += ` --modloader ${modloader}`;

  document.getElementById('log').textContent = '> ' + cmd + '\n';

  const child = exec(cmd);
  child.stdout.on('data', d => document.getElementById('log').textContent += d);
  child.stderr.on('data', d => document.getElementById('log').textContent += d);
  child.on('close', c  => document.getElementById('log').textContent += `\n[Process exited ${c}]`);
}

window.launchMinecraft = launchMinecraft;
