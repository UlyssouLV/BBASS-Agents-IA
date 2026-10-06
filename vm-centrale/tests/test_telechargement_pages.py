import ssl

import truststore

from vm_centrale import telechargement_pages


def test_client_des_pages_verifie_les_certificats_avec_le_magasin_du_systeme(monkeypatch):
    # #129 : certains sites publics n'envoient pas leur certificat
    # intermédiaire ; certifi échoue, le magasin du système le complète
    # (Windows, macOS). La vérification reste toujours active.
    arguments = {}

    def client_espion(**kwargs):
        arguments.update(kwargs)
        return object()

    monkeypatch.setattr(telechargement_pages.httpx, "Client", client_espion)

    telechargement_pages._creer_client_http()

    contexte = arguments["verify"]
    assert isinstance(contexte, truststore.SSLContext)
    assert contexte.verify_mode == ssl.CERT_REQUIRED
    assert contexte.check_hostname is True
    assert arguments["follow_redirects"] is True
