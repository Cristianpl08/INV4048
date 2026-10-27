import unittest
from prepare_existing_ad import narration_only


class ExistingAD(unittest.TestCase):
    def test_removes_analysis_without_rewriting_narration(self):
        text = 'Dos hombres bailan con energía.\n\n- **Mecanismo de Atención - Personajes**: Explicación.\nResumen:\n* Emoción complementaria: Éxtasis'
        self.assertEqual(narration_only(text), 'Dos hombres bailan con energía.')

    def test_removes_counters_and_orphan_markdown(self):
        self.assertEqual(narration_only('Un bebé gatea.\n\n- Emoción complementaria utilizada: Aceptación'), 'Un bebé gatea.')
        self.assertEqual(narration_only('El caballo avanza.\n\n**'), 'El caballo avanza.')

    def test_preserves_multiline_text_and_rejects_empty(self):
        self.assertEqual(narration_only('Un niño juega.\nCerca, un perro observa.'), 'Un niño juega.\nCerca, un perro observa.')
        with self.assertRaises(ValueError): narration_only('**')


if __name__ == '__main__': unittest.main()
