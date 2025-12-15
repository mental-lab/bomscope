"""
Tests for dependency manifest parsers.
"""

import os
import tempfile
import unittest
from repo_analyzer.parsers import (
    parse_python_requirements, 
    parse_pyproject_toml, 
    parse_pipfile, 
    parse_setup_py,
    parse_java_pom,
    parse_gradle_build,
    parse_manifest_file
)


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


class TestPipfileParser(unittest.TestCase):
    """Test Pipfile parsing."""
    
    def test_parse_pipfile_dependencies(self):
        """Test parsing Pipfile format."""
        content = """[packages]
flask = "==2.3.0"
requests = ">=2.28.0"

[dev-packages]
pytest = ">=7.0.0"
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_pipfile(f.name)
            
            self.assertEqual(len(deps), 3)
            self.assertIn(('flask', '==2.3.0'), deps)
            self.assertIn(('requests', '>=2.28.0'), deps)
            self.assertIn(('pytest', '>=7.0.0'), deps)
            
            os.unlink(f.name)

    def test_parse_pipfile_packages_only(self):
        """Test parsing Pipfile with only [packages] section."""
        content = """[packages]
numpy = "~=1.24.0"
pandas = "*"
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_pipfile(f.name)
            
            self.assertEqual(len(deps), 2)
            self.assertIn(('numpy', '~=1.24.0'), deps)
            self.assertIn(('pandas', '*'), deps)
            
            os.unlink(f.name)


class TestSetupPyParser(unittest.TestCase):
    """Test setup.py parsing."""
    
    def test_parse_setup_py_dependencies(self):
        """Test parsing setup.py install_requires."""
        content = """from setuptools import setup

setup(
    name="test-package",
    install_requires=[
        "flask>=2.3.0",
        "requests>=2.28.0",
    ],
)
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_setup_py(f.name)
            
            self.assertEqual(len(deps), 2)
            self.assertEqual(deps[0], ('flask', '>=2.3.0'))
            self.assertEqual(deps[1], ('requests', '>=2.28.0'))
            
            os.unlink(f.name)

    def test_parse_setup_py_multiline(self):
        """Test parsing setup.py with multiline install_requires."""
        content = """from setuptools import setup, find_packages

setup(
    name="sample-package",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "flask>=2.3.0",
        "requests>=2.28.0",
        "numpy~=1.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black",
        ]
    }
)
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_setup_py(f.name)
            
            self.assertEqual(len(deps), 3)
            self.assertIn(('flask', '>=2.3.0'), deps)
            self.assertIn(('requests', '>=2.28.0'), deps)
            self.assertIn(('numpy', '~=1.24.0'), deps)
            
            os.unlink(f.name)


class TestJavaPomParser(unittest.TestCase):
    """Test Java pom.xml parsing."""
    
    def test_parse_pom_dependencies(self):
        """Test parsing Maven pom.xml dependencies."""
        content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>5.3.21</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
        </dependency>
    </dependencies>
</project>"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_java_pom(f.name)
            
            self.assertEqual(len(deps), 2)
            self.assertIn(('org.springframework:spring-core', '5.3.21'), deps)
            self.assertIn(('junit:junit', '4.13.2'), deps)
            
            os.unlink(f.name)


class TestGradleBuildParser(unittest.TestCase):
    """Test Gradle build.gradle parsing."""
    
    def test_parse_gradle_dependencies(self):
        """Test parsing Gradle build.gradle dependencies."""
        content = """
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web:2.7.0'
    testImplementation 'junit:junit:4.13.2'
    api 'com.fasterxml.jackson.core:jackson-core:2.13.3'
    compile 'org.slf4j:slf4j-api:1.7.36'
}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gradle', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_gradle_build(f.name)
            
            self.assertEqual(len(deps), 4)
            self.assertIn(('org.springframework.boot:spring-boot-starter-web', '2.7.0'), deps)
            self.assertIn(('junit:junit', '4.13.2'), deps)
            self.assertIn(('com.fasterxml.jackson.core:jackson-core', '2.13.3'), deps)
            self.assertIn(('org.slf4j:slf4j-api', '1.7.36'), deps)
            
            os.unlink(f.name)

    def test_parse_gradle_parentheses_syntax(self):
        """Test parsing Gradle dependencies with parentheses syntax."""
        content = """
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web:2.7.0")
    testImplementation("junit:junit:4.13.2")
}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gradle', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_gradle_build(f.name)
            
            self.assertEqual(len(deps), 2)
            self.assertIn(('org.springframework.boot:spring-boot-starter-web', '2.7.0'), deps)
            self.assertIn(('junit:junit', '4.13.2'), deps)
            
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
    
    def test_pipfile_detection(self):
        """Test that Pipfile files are detected correctly."""
        content = """[packages]
requests = ">=2.28.0"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='Pipfile', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_manifest_file(f.name)
            
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0], ('requests', '>=2.28.0'))
            
            os.unlink(f.name)
    
    def test_setup_py_detection(self):
        """Test that setup.py files are detected correctly."""
        content = """from setuptools import setup

setup(
    name="test-package",
    install_requires=[
        "flask>=2.3.0",
    ],
)
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='setup.py', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_manifest_file(f.name)
            
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0], ('flask', '>=2.3.0'))
            
            os.unlink(f.name)
    
    def test_pom_xml_detection(self):
        """Test that pom.xml files are detected correctly."""
        content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
        </dependency>
    </dependencies>
</project>"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='pom.xml', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_manifest_file(f.name)
            
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0], ('junit:junit', '4.13.2'))
            
            os.unlink(f.name)
    
    def test_build_gradle_detection(self):
        """Test that build.gradle files are detected correctly."""
        content = """
dependencies {
    implementation 'org.springframework:spring-core:5.3.21'
}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='build.gradle', delete=False) as f:
            f.write(content)
            f.flush()
            
            deps = parse_manifest_file(f.name)
            
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0], ('org.springframework:spring-core', '5.3.21'))
            
            os.unlink(f.name)
    
    def test_unsupported_file_type(self):
        """Test that unsupported file types raise ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_manifest_file('package.json')  # JavaScript file not yet supported
        
        self.assertIn('Unsupported manifest file type', str(context.exception))


if __name__ == '__main__':
    unittest.main()
