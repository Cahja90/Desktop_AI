#tests fuer warteschlange
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import warteschlange as w


class TestWarteschlange(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hub = Path(self.tmp.name)
        self.dev = self.hub / "dev"
        self.dev.mkdir()
        (self.hub / "projekte").mkdir()
        (self.hub / "projekte" / "liste.yaml").write_text(
            "konto: x\nprojekte:\n  - name: alpha\n  - name: beta\n",
            encoding="utf-8",
        )
        (self.hub / "alpha").mkdir()
        (self.hub / "beta").mkdir()
        (self.dev / "einstellungen.json").write_text(
            json.dumps(
                {
                    "max_gleichzeitig": 2,
                    "timeout_minuten": 45,
                    "max_laeufe_pro_tag": 20,
                    "toast_an": False,
                }
            ),
            encoding="utf-8",
        )
        (self.dev / "queue.json").write_text('{"auftraege": []}\n', encoding="utf-8")
        (self.dev / "status.json").write_text(
            '{"tag": "", "laeufe_heute": 0, "projekte": {}}\n',
            encoding="utf-8",
        )
        (self.dev / "starte.ps1").write_text("#noop\n", encoding="utf-8")
        self.pfade = w.hub_pfade(self.hub)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_liste(self):
        namen = w.parse_liste_namen(self.pfade["liste"])
        self.assertEqual(namen, ["alpha", "beta"])

    def test_einreihen_alles(self):
        jobs = w.einreihen(self.pfade, "alles", "pflege alles", "vorschlagen")
        self.assertEqual(len(jobs), 2)
        queue = w.lies_json(self.pfade["queue"], {})
        self.assertEqual(len(queue["auftraege"]), 2)
        status = w.status_lesen(self.pfade)
        self.assertEqual(status["projekte"]["alpha"]["zustand"], "wartet")

    def test_lock_pro_projekt(self):
        status = {
            "tag": w.heute(),
            "laeufe_heute": 0,
            "projekte": {
                "alpha": w.leerer_eintrag("alpha", str(self.hub / "alpha")),
            },
        }
        status["projekte"]["alpha"]["zustand"] = "laeuft"
        status["projekte"]["alpha"]["pid"] = 1
        queue = {
            "auftraege": [
                {"id": "1", "projekt": "alpha", "auftrag": "a", "modus": "vorschlagen", "stand": "wartet"},
                {"id": "2", "projekt": "beta", "auftrag": "b", "modus": "vorschlagen", "stand": "wartet"},
            ]
        }
        jobs = w.naechste_jobs(queue, status, 2)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["projekt"], "beta")

    def test_max_gleichzeitig(self):
        status = {
            "tag": w.heute(),
            "laeufe_heute": 0,
            "projekte": {
                "alpha": {**w.leerer_eintrag("alpha", "x"), "zustand": "laeuft", "pid": 1},
                "beta": {**w.leerer_eintrag("beta", "y"), "zustand": "laeuft", "pid": 2},
            },
        }
        queue = {
            "auftraege": [
                {"id": "3", "projekt": "gamma", "auftrag": "c", "modus": "vorschlagen", "stand": "wartet"},
            ]
        }
        jobs = w.naechste_jobs(queue, status, 2)
        self.assertEqual(jobs, [])

    def test_timeout_faellig(self):
        start = (datetime.now() - timedelta(minutes=50)).strftime("%Y-%m-%dT%H:%M:%S")
        eintrag = {"zustand": "laeuft", "start": start, "pid": 9}
        self.assertTrue(w.timeout_faellig(eintrag, 45))
        frisch = {"zustand": "laeuft", "start": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "pid": 9}
        self.assertFalse(w.timeout_faellig(frisch, 45))

    def test_tageslimit_reset(self):
        status = {"tag": "2000-01-01", "laeufe_heute": 99, "projekte": {}}
        neu = w.sichere_status(status, tag=w.heute())
        self.assertEqual(neu["laeufe_heute"], 0)
        self.assertEqual(neu["tag"], w.heute())

    def test_kill_pid_ungueltig(self):
        self.assertFalse(w.kill_pid(None))
        self.assertFalse(w.kill_pid("x"))


if __name__ == "__main__":
    unittest.main()
