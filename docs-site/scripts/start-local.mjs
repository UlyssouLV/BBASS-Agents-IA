/**
 * Démarrage local : polling FS (lecteur réseau H: — le watch natif plante).
 */
import {spawn} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const env = {
  ...process.env,
  WATCHPACK_POLLING: 'true',
  CHOKIDAR_USEPOLLING: '1',
};

const child = spawn(
  process.platform === 'win32' ? 'npx.cmd' : 'npx',
  ['docusaurus', 'start', '--host', '127.0.0.1'],
  {cwd: root, env, stdio: 'inherit', shell: true},
);

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 1);
  }
});
