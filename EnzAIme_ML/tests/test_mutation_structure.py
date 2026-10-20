"""Real evidence integration plus synthetic geometry fixtures for edge cases."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.mutations import router
from backend.app.services.mutation import mutation_evidence, preview_mutations, protein_catalog
from backend.app.services.structure import inspect_structure, parse_pdb, RESIDUES

NAMES = {value: key for key, value in RESIDUES.items()}


def atom(residue, number, serial=1, chain="A", insertion="", alt="", occupancy=1, x=0):
    return (f"ATOM  {serial:5d}  CA {alt:1}{NAMES[residue]:3} {chain:1}{number:4d}{insertion:1}   "
            f"{x:8.3f}{0:8.3f}{0:8.3f}{occupancy:6.2f}{20:6.2f}           C")


def pdb(sequence, chain="A", start=100):
    return "\n".join(atom(aa, start+i, i+1, chain=chain, x=i*3.8) for i, aa in enumerate(sequence))


class MutationTests(unittest.TestCase):
    def test_real_catalog_and_multimutant(self):
        self.assertEqual(len(protein_catalog()), 25)
        result = preview_mutations("42", "V235I, A306E")
        self.assertEqual(result["mutant_sequence"][234], "I")
        self.assertEqual(result["mutant_sequence"][305], "E")
        self.assertEqual(len(result["mutant_sequence"]), 342)
        self.assertEqual(sum(a != b for a, b in zip(result["reference_sequence"], result["mutant_sequence"])), 2)
        self.assertIsNone(result["stability_prediction"])

    def test_invalid_substitutions(self):
        for text in ["", "V0I", "V235V", "V235I,V235A", "A235I", "V9999I", "X235I", "V235*", "V235Ijunk"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                preview_mutations("42", text)
        with self.assertRaises(LookupError):
            preview_mutations("unknown", "S1A")

    def test_real_evidence_not_misrepresented(self):
        result = mutation_evidence("42")
        self.assertEqual(len(result["records"]), 10)
        self.assertEqual(sum(bool(r["substitutions"]) for r in result["records"]), 8)
        self.assertTrue(all("unresolved" in r["sequence_identity_status"] for r in result["records"]))
        self.assertTrue(all("DDG" not in r["measurements"] for r in result["records"]))
        self.assertEqual(mutation_evidence("1")["status"], "no_records")


class StructureTests(unittest.TestCase):
    def test_signal_offset_insertion_and_site_neighbors(self):
        reference = "MMMMMACDEFGHIKLMNPQRSTVWY"
        text = pdb(reference[5:])
        with patch("backend.app.services.structure.get_protein", return_value={"sequence": reference}):
            result = inspect_structure("test", text, position=7)
        self.assertEqual(result["status"], "mapped")
        self.assertEqual(result["reference_start"], 6)
        self.assertEqual(result["site"]["residue_number"], 101)
        self.assertEqual(result["neighbors"][0]["ca_distance_angstrom"], 3.8)
        self.assertEqual(len(result["sha256"]), 64)

    def test_first_model_altloc_and_insertion_codes(self):
        text = "MODEL        1\n" + "\n".join([
            atom("A", 10, insertion="A", alt="A", occupancy=.2, x=1),
            atom("A", 10, insertion="A", alt="B", occupancy=.8, x=2),
            atom("C", 10, insertion="B", x=3),
        ]) + "\nENDMDL\nMODEL        2\n" + atom("D", 20) + "\nENDMDL"
        chains, model = parse_pdb(text)
        self.assertEqual(model, "1")
        self.assertEqual(len(chains["A"]), 2)
        self.assertEqual(chains["A"][0]["xyz"][0], 2)
        self.assertEqual(chains["A"][1]["insertion_code"], "B")

    def test_ambiguous_mismatched_and_short_mapping(self):
        motif = "ACDEFGHIKLMN"
        for sequence, observed in [(motif*2, motif), (motif, "AACDEFGHIKLMN"), (motif, "ACD")]:
            with self.subTest(sequence=sequence), patch("backend.app.services.structure.get_protein", return_value={"sequence": sequence}):
                result = inspect_structure("test", pdb(observed), position=2)
                self.assertEqual(result["status"], "unresolved")
                self.assertIsNone(result["site"])
                self.assertTrue(all(r["sequence_position"] is None for r in result["residues"]))

    def test_chain_selection_and_unobserved_site(self):
        sequence = protein_catalog()["1"]["sequence"]
        text = pdb(sequence[25:45], chain="A") + "\n" + pdb(sequence[25:45], chain="B")
        self.assertEqual(inspect_structure("1", text)["status"], "select_chain")
        result = inspect_structure("1", text, "B", 1)
        self.assertEqual(result["status"], "mapped")
        self.assertEqual(result["site_status"], "unmapped")
        with self.assertRaises(ValueError):
            inspect_structure("1", text, "Z")

    def test_bad_coordinates(self):
        for text in ["data_mmcif", "ATOM      1  CA ", atom("A", 1, x=float("nan")), atom("A", 1, occupancy=-1)]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_pdb(text)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        cls.client = TestClient(app)

    def test_real_endpoints_and_errors(self):
        self.assertEqual(len(self.client.get("/api/mutation-proteins").json()["proteins"]), 25)
        self.assertEqual(len(self.client.get("/api/mutations/42/evidence").json()["records"]), 10)
        self.assertEqual(self.client.get("/api/mutations/999/evidence").status_code, 404)
        response = self.client.post("/api/mutations/preview", json={"protein_id": "42", "substitutions": "V235I"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mutant_sequence"][234], "I")
        self.assertEqual(self.client.post("/api/mutations/preview", json={"protein_id": "42", "substitutions": "A235I"}).status_code, 422)
        for position in [0, 1.5, True]:
            response = self.client.post("/api/structures/inspect", json={"protein_id": "1", "pdb_text": "bad", "position": position})
            self.assertEqual(response.status_code, 422)
        response = self.client.post("/api/structures/inspect", json={"protein_id": "1", "pdb_text": "x"*2_000_001})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
