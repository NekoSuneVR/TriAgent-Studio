import unittest
from app.project_templates import files_for

class UnityTemplateTests(unittest.TestCase):
    def test_udon_template_files(self):
        files=files_for('vrchat-udonsharp','Example')
        self.assertIn('Assets/UdonScripts/ExampleInteractable.cs',files)
        self.assertIn('UdonSharpBehaviour',files['Assets/UdonScripts/ExampleInteractable.cs'])
        self.assertIn('[Ll]ibrary/',files['.gitignore'])
        self.assertIn('AGENTS.md',files)
    def test_unity_template(self):
        self.assertIn('.gitignore',files_for('unity','Demo'))
    def test_invalid_template(self):
        with self.assertRaises(ValueError): files_for('unknown','Demo')

if __name__=='__main__':
    unittest.main()
