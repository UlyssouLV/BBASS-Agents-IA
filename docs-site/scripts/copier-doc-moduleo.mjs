/**
 * Copie la doc Moduléo versionnée à côté du client (WADL et page de
 * documentation du serveur du cabinet) dans static/moduleo/, pour l'ouvrir
 * depuis la feature « Branchement Moduléo ». Les sources restent dans
 * vm-centrale (régénérées par scripts/telecharger_doc_moduleo.py).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ici = path.dirname(fileURLToPath(import.meta.url));
const source = path.resolve(ici, '../../vm-centrale/src/vm_centrale/moduleo/docs');
const sortie = path.resolve(ici, '../static/moduleo');

// La page du serveur a des liens absolus (« /Content/css/… »,
// « /api/documentation/Api/… ») : la base les renvoie vers le serveur du
// cabinet (MODULEO_URL par défaut, vm-centrale/src/vm_centrale/config.py).
const SERVEUR = 'https://mwa-bbass.kipaware.fr/';

fs.mkdirSync(sortie, { recursive: true });
fs.copyFileSync(path.join(source, 'wadl.xml'), path.join(sortie, 'wadl.xml'));
const page = fs.readFileSync(path.join(source, 'documentation.html'), 'utf8');
fs.writeFileSync(
  path.join(sortie, 'documentation.html'),
  page.replace(/<head>/i, `<head>\n    <base href="${SERVEUR}" target="_blank" />`),
);
console.log(`Doc Moduléo copiée dans ${path.relative(process.cwd(), sortie)}`);
