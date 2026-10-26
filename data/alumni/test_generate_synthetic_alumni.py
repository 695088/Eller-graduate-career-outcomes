"""Run with: python3 -m unittest discover -s data/alumni -p 'test_*.py' -v"""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

import generate_synthetic_alumni as generator


class SyntheticAlumniTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs = generator.load_references(generator.ROOT)
        cls.records = generator.generate_records(450, 42, 2018, 2022, cls.refs)

    def test_seed_reproduces_records(self):
        self.assertEqual(self.records, generator.generate_records(450, 42, 2018, 2022, self.refs))
        self.assertNotEqual(self.records, generator.generate_records(450, 43, 2018, 2022, self.refs))

    def test_references_and_outcome_edge_cases(self):
        self.assertEqual(set(generator.MAJOR_SUBJECTS), {r['major'] for r in self.records})
        self.assertEqual({True, False}, {r['had_internship'] for r in self.records})
        self.assertEqual({True, False}, {r['promoted_within_3yr'] for r in self.records})
        self.assertTrue(any(r['secondary_major'] is None for r in self.records))
        self.assertTrue(any(r['secondary_major'] is not None for r in self.records))
        for row in self.records:
            self.assertEqual(21, len(row))
            self.assertTrue(2018 <= row['grad_year'] <= 2022)
            self.assertTrue(set(row['courses_taken']) <= self.refs['courses'].keys())
            self.assertTrue(set(row['skills_obtained']) <= self.refs['skills'])
            self.assertIn(row['first_onet_soc'], self.refs['occupations'])
            self.assertIn(row['yr3_onet_soc'], self.refs['occupations'])
            if row['promoted_within_3yr']:
                self.assertTrue(0 < row['months_to_promo'] <= 36)
            else:
                self.assertIsNone(row['months_to_promo'])
        band_four = generator.SALARY_BANDS[3]
        self.assertEqual((4, 70000, 80000, 75000.0), tuple(band_four.values()))

    def test_csv_round_trip_preserves_arrays_nulls_and_booleans(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'alumni.csv'
            generator.write_csv(path, generator.FIELDS, self.records)
            with path.open(newline='', encoding='utf-8') as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(generator.FIELDS, reader.fieldnames)
                loaded = list(reader)
        for original, saved in zip(self.records, loaded):
            self.assertEqual(original['courses_taken'], json.loads(saved['courses_taken']))
            self.assertEqual(original['skills_obtained'], json.loads(saved['skills_obtained']))
            self.assertEqual(original['had_internship'], saved['had_internship'] == 'true')
            self.assertEqual(original['promoted_within_3yr'], saved['promoted_within_3yr'] == 'true')
            for field in ('secondary_major', 'internship_employer', 'months_to_promo'):
                if original[field] is None:
                    self.assertEqual('', saved[field])

    def test_invalid_records_are_rejected(self):
        for field, value in [('skills_obtained', ['SK_NONEXISTENT']),
                             ('first_onet_soc', '99-9999.99'),
                             ('starting_salary_mid', 1.0),
                             ('gpa_final', 4.1),
                             ('alumni_id', 'ALU_' + 'x' * 20)]:
            with self.subTest(field=field):
                row = copy.deepcopy(self.records[0])
                row[field] = value
                with self.assertRaises(ValueError):
                    generator.validate_records([row], self.refs)

    def test_invalid_generation_arguments(self):
        for arguments in [(0, 42, 2018, 2022), (1, 42, 2023, 2022)]:
            with self.assertRaises(ValueError):
                generator.generate_records(*arguments, self.refs)
        self.assertEqual(1, len(generator.generate_records(1, 0, 2022, 2022, self.refs)))


if __name__ == '__main__':
    unittest.main()
