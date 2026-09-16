from vm_centrale.concurrence import CacheIdempotence, VerrousParCompte


def test_verrous_par_compte_renvoie_le_meme_verrou_pour_le_meme_compte():
    verrous = VerrousParCompte()

    assert verrous.pour("j.dupont") is verrous.pour("j.dupont")


def test_verrous_par_compte_renvoie_des_verrous_distincts_pour_des_comptes_distincts():
    verrous = VerrousParCompte()

    assert verrous.pour("j.dupont") is not verrous.pour("n.durand")


def test_cache_idempotence_renvoie_la_reponse_enregistree_pour_la_meme_cle():
    cache = CacheIdempotence()

    cache.enregistrer("j.dupont", "cle-1", {"reponse": "x"})

    assert cache.recuperer("j.dupont", "cle-1") == {"reponse": "x"}


def test_cache_idempotence_ignore_une_cle_dun_autre_compte():
    cache = CacheIdempotence()

    cache.enregistrer("j.dupont", "cle-1", {"reponse": "x"})

    assert cache.recuperer("n.durand", "cle-1") is None


def test_cache_idempotence_renvoie_none_pour_une_cle_inconnue():
    cache = CacheIdempotence()

    assert cache.recuperer("j.dupont", "cle-inconnue") is None


def test_cache_idempotence_purge_les_entrees_perimees():
    cache = CacheIdempotence()
    cache.enregistrer("j.dupont", "cle-1", {"reponse": "x"})
    # Rembobine l'horodatage de l'entrée pour simuler son expiration, plutôt
    # qu'attendre réellement _DUREE_CONSERVATION_SECONDES dans le test.
    cle_interne = ("j.dupont", "cle-1")
    horodatage, valeur = cache._entrees[cle_interne]
    cache._entrees[cle_interne] = (horodatage - 301, valeur)

    assert cache.recuperer("j.dupont", "cle-1") is None
    assert cle_interne not in cache._entrees
