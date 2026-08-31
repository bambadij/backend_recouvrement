"""Tests du calcul du DSO.

Le DSO est le seul indicateur du service qui applique une formule plutôt que de
transmettre un agrégat SQL. C'est donc le seul endroit où une erreur d'arithmétique
peut passer inaperçue : une requête fausse renvoie des chiffres visiblement absurdes,
un ratio faux renvoie un nombre plausible.
"""

from decimal import Decimal

import pytest

from app.organisations.stats import OrganisationStatsService

calculer = OrganisationStatsService.calculer_dso


class TestFluxAbsent:
    """Sans flux confié sur la fenêtre, le ratio n'existe pas."""

    def test_flux_nul_renvoie_none(self):
        # Et surtout pas 0, qui se lirait « tout encaissé le jour même ».
        assert calculer(Decimal("5000000"), Decimal("0"), 90) is None

    def test_flux_negatif_renvoie_none(self):
        # Ne doit pas arriver, mais un montant négatif ne doit jamais produire
        # un DSO négatif présenté comme une performance.
        assert calculer(Decimal("5000000"), Decimal("-100"), 90) is None

    def test_encours_et_flux_nuls_renvoie_none(self):
        assert calculer(Decimal("0"), Decimal("0"), 90) is None


class TestCasConnus:
    def test_un_tiers_de_la_fenetre(self):
        # 100 / 300 x 90 = 30 jours
        assert calculer(Decimal("100"), Decimal("300"), 90) == 30

    def test_encours_egal_au_flux_donne_la_fenetre_entiere(self):
        # Tout ce qui a été confié est encore dû : le DSO vaut la fenêtre.
        assert calculer(Decimal("600"), Decimal("600"), 90) == 90

    def test_encours_nul_donne_zero(self):
        # Ici 0 est la vérité : tout est rentré.
        assert calculer(Decimal("0"), Decimal("300"), 90) == 0

    def test_encours_superieur_au_flux_depasse_la_fenetre(self):
        # Cas réel d'un portefeuille ancien : l'encours accumulé dépasse le flux
        # récent, donc le DSO dépasse la fenêtre. Ce n'est pas une anomalie.
        assert calculer(Decimal("1200"), Decimal("600"), 90) == 180


class TestArrondi:
    def test_arrondi_au_jour_le_plus_proche(self):
        # 1000 / 3000 x 100 = 33,33... -> 33
        assert calculer(Decimal("1000"), Decimal("3000"), 100) == 33

    def test_arrondi_superieur(self):
        # 2000 / 3000 x 100 = 66,66... -> 67
        assert calculer(Decimal("2000"), Decimal("3000"), 100) == 67

    def test_resultat_toujours_entier(self):
        assert isinstance(calculer(Decimal("1000"), Decimal("3000"), 100), int)


class TestFenetre:
    @pytest.mark.parametrize(
        ("periode", "attendu"),
        [(30, 10), (90, 30), (365, 122)],
    )
    def test_le_dso_est_proportionnel_a_la_fenetre(self, periode, attendu):
        """A flux constant, le DSO croît avec la fenêtre.

        Ce n'est pas un défaut du calcul mais sa nature : le DSO n'est comparable
        qu'à fenêtre égale. Le test fige ce comportement pour qu'un futur
        « correctif » qui tenterait de le normaliser soit signalé.
        """
        assert calculer(Decimal("100"), Decimal("300"), periode) == attendu


class TestDonneesReelles:
    def test_cas_observe_en_base(self):
        # Relevé sur l'organisation 1 : encours 20 838 156, flux 30 355 500 sur 90 j.
        # 0,6864... x 90 = 61,77 -> 62
        assert calculer(Decimal("20838156.00"), Decimal("30355500.00"), 90) == 62
