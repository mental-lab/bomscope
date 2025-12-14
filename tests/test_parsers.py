"""
Tests for dependency manifest parsers.
"""

import os
import tempfile
import unittest
from repo_analyzer.parsers import parse_python_requirements, parse_pyproject_toml, parse_manifest_file


class TestPythonRequirementsParser(unittest.TestCase):
    """Test Python requirements.txt parsing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_content = """# Core dependencies
flask==2.3.0
requests>=2.28.0
numpy~=1.24.0

# Development dependencies  
pytest>=7.0.0
black

# Comments and edge cases
django>=4.0,<5.0

# Empty line above
-e git+https://github.com/user/repo.git#egg=mypackage
-r other-requirements.txt
"""
    
    def test_parse_basic_requirements(self):
        """Test parsing basic package==version format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("flask==2.3.0\nrequests>=2.28.0\n")
            f.flush()
            
            deps = parse_python_requirements(f.name)
            
            self.assertEqual(len(deps), 2)
            self.assertEqual(deps[0], ('flask', '==2.3.0'))
            self.assertEqual(deps[1], ('requests', '>=2.28.0'))
            
            os.unlink(f.name)
    
    def test_skip_comments_and_options(self):
        """Test that comments and pip options are skipped."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(self.test_content)
            f.flush()
            
            deps = parse_python_requirements(f.name)
            
            # Should only get actual packages, not comments or pip options
            expected_packages = ['flask', 'requests', 'numpy', 'pytest', 'black', 'django']
            actual_packages = [name for name, version in deps]
            
            self.assertEqual(len(deps), 6)
            self.assertEqual(actual_packages, expected_packages)
            
            os.unlink(f.name)
    
    def test_version_specifiers(self):
        """Test different version specifier formats."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("flask==2.3.0\nrequests>=2.28.0\nnumpy~=1.24.0\ndjango>=4.0,<5.0\n")
            f.flush()
            
            deps = parse_python_requirements(f.name)
            
            self.assertEqual(deps[0][1], '==2.3.0')
            self.assertEqual(deps[1][1], '>=2.28.0')
            self.assertEqual(deps[2][1], '~=1.24.0')
            self.assertEqual(deps[3][1], '>=4.0,<5.0')
            
            os.unlink(f.name)
    
    def test_empty_file(self):
        """Test parsing empty requirements file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# Only comments\n\n# Nothing else\n")
            f.flush()
            
            deps = parse_python_requirements(f.name)
            
            self.assertEqual(len(deps), 0)
            
            os.unlink(f.name)


class TestPyprojectTomlParser(unittest.TestCase):
    """Test pyproject.toml parsing."""
    
    def test_parse_poetry_dependencies(self):
        """Test parsing Poetry format pyproject.toml."""
        content = """[tool.poetry.dependencies]
python = "^3.9"
flask = "^2.3.0"
requests = ">=2.28.0"

[tool.poetry.dev-dependencies]
pytest = "^7.0.0"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_pyproject_toml(f.name)
            
            # Should skip python version, include others
            self.assertEqual(len(deps), 3)
            self.assertIn(('flask', '^2.3.0'), deps)
            self.assertIn(('requests', '>=2.28.0'), deps)
            self.assertIn(('pytest', '^7.0.0'), deps)
            
            os.unlink(f.name)

    def test_parse_pep621_dependencies(self):
        """Test parsing PEP 621 format pyproject.toml."""
        content = """[project.dependencies]
flask = ">=2.3.0"
requests = "~=2.28.0"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_pyproject_toml(f.name)
            
            self.assertEqual(len(deps), 2)
            self.assertIn(('flask', '>=2.3.0'), deps)
            self.assertIn(('requests', '~=2.28.0'), deps)
            
            os.unlink(f.name)


class TestManifestFileParser(unittest.TestCase):
    """Test manifest file auto-detection."""
    
    def test_requirements_txt_detection(self):
        """Test that requirements.txt files are detected correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='requirements.txt', delete=False) as f:
            f.write("flask==2.3.0\n")
            f.flush()
            
            deps = parse_manifest_file(f.name)
            
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0], ('flask', '==2.3.0'))
            
            os.unlink(f.name)
    
    def test_pyproject_toml_detection(self):
        """Test that pyproject.toml files are detected correctly."""
        content = """[tool.poetry.dependencies]
flask = "^2.3.0"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='pyproject.toml', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_manifest_file(f.name)
            
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0], ('flask', '^2.3.0'))
            
            os.unlink(f.name)
    
    def test_unsupported_file_type(self):
        """Test that unsupported file types raise ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_manifest_file('pom.xml')
        
        self.assertIn('Unsupported manifest file type', str(context.exception))


if __name__ == '__main__':
    unittest.main()
