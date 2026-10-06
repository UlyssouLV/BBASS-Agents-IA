import itertools
import ssl

import httpx
import pytest
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


def _servir(monkeypatch, gestionnaire) -> None:
    # Transport factice : aucun accès réseau, le vrai TelechargeurHttpx lit
    # la réponse en flux comme en production.
    client = httpx.Client(transport=httpx.MockTransport(gestionnaire))
    monkeypatch.setattr(telechargement_pages, "_http_client", client)


class _CorpsInterdit(httpx.SyncByteStream):
    # Échoue si le téléchargeur lit le corps.
    def __iter__(self):
        raise AssertionError("corps lu alors qu'il devait être ignoré")


def test_une_page_html_est_lue_et_decodee_selon_son_charset(monkeypatch):
    _servir(
        monkeypatch,
        lambda requete: httpx.Response(
            200, headers={"content-type": "text/html; charset=iso-8859-1"}, content="Été".encode("latin-1")
        ),
    )

    page = telechargement_pages.TelechargeurHttpx().telecharger("https://exemple.fr")

    assert page == telechargement_pages.PageTelechargee(200, "text/html; charset=iso-8859-1", "Été")


def test_le_corps_dun_contenu_non_html_nest_jamais_lu(monkeypatch):
    _servir(
        monkeypatch,
        lambda requete: httpx.Response(200, headers={"content-type": "application/pdf"}, stream=_CorpsInterdit()),
    )

    page = telechargement_pages.TelechargeurHttpx().telecharger("https://exemple.fr/rapport.pdf")

    assert page == telechargement_pages.PageTelechargee(200, "application/pdf", "")


def test_une_page_trop_lourde_est_abandonnee_en_cours_de_lecture(monkeypatch):
    monkeypatch.setattr(telechargement_pages, "_TAILLE_MAX_PAGE", 10)
    _servir(
        monkeypatch,
        lambda requete: httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 11),
    )

    with pytest.raises(telechargement_pages.PageIndisponible, match="octets"):
        telechargement_pages.TelechargeurHttpx().telecharger("https://exemple.fr")


def test_une_page_servie_au_compte_gouttes_est_abandonnee_au_dela_du_delai_global(monkeypatch):
    # Chaque morceau arrive sous le timeout par lecture, mais la page entière
    # dépasse PAGES_HTTP_TIMEOUT.
    horloge = itertools.count(0, 4)
    monkeypatch.setattr(telechargement_pages.time, "monotonic", lambda: next(horloge))
    class _AuCompteGouttes(httpx.SyncByteStream):
        def __iter__(self):
            while True:
                yield b"x"

    _servir(
        monkeypatch,
        lambda requete: httpx.Response(200, headers={"content-type": "text/html"}, stream=_AuCompteGouttes()),
    )

    with pytest.raises(telechargement_pages.PageIndisponible, match="délai"):
        telechargement_pages.TelechargeurHttpx().telecharger("https://exemple.fr")
