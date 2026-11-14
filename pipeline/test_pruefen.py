import unittest

from pipeline.pruefen import pruefe_profil, sammle_punkte
from pipeline.schiffen import aktion, darf_schiffen


class TestPruefen(unittest.TestCase):
    def test_volles_readme_ist_leer(self) -> None:
        #alles vorhanden, liste bleibt leer
        readme_text = "Problem Ablauf privat How Produktionscode Screenshot"
        punkte = sammle_punkte(
            readme_text,
            "kurze beschreibung",
            ["ai"],
            False,
            True,
            ["ai"],
        )
        self.assertEqual(punkte, [])

    def test_leerer_text_meldet_luecken(self) -> None:
        #leerer text, mehrere punkte
        punkte = sammle_punkte("", "", [], False, True, ["ai"])
        self.assertIn("beispiel fehlt", punkte)
        self.assertIn("saas-satz fehlt", punkte)
        self.assertGreater(len(punkte), 1)

    def test_profil_ohne_email_mit_klarname(self) -> None:
        #beide meldungen
        meldungen = pruefe_profil(False, True, True, True, False, False)
        self.assertIn("e-mail datei fehlt", meldungen)
        self.assertIn("klarname steht drin", meldungen)

    def test_schiffen_auswahl(self) -> None:
        #hoch darf, zu nicht, ohne code als text
        self.assertFalse(darf_schiffen("zu"))
        self.assertTrue(darf_schiffen("hoch"))
        self.assertEqual(aktion("ohne_code"), "ohne code")
