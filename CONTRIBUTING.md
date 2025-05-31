# 🤝 Contributing to Google Account Creator

Thank you for your interest in contributing to the Google Account Creator project! This document provides guidelines and instructions for contributing to ensure a smooth and efficient collaboration process.

## 📋 Table of Contents

- [🎯 Getting Started](#-getting-started)
- [💻 Development Setup](#-development-setup)
- [🏗️ Development Workflow](#-development-workflow)
- [📝 Coding Standards](#-coding-standards)
- [🧪 Testing Guidelines](#-testing-guidelines)
- [📚 Documentation](#-documentation)
- [🔍 Code Review Process](#-code-review-process)
- [🐛 Bug Reports](#-bug-reports)
- [✨ Feature Requests](#-feature-requests)
- [🏆 Recognition](#-recognition)
- [❓ Getting Help](#-getting-help)

## 🎯 Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.10+** installed
- **Git** for version control
- **Docker** (optional, for containerized development)
- **Android SDK/ADB** for device testing
- Basic understanding of async/await patterns
- Familiarity with performance optimization concepts

### First Steps

1. **📋 Check Issues**: Look for existing issues or create new ones
2. **🍴 Fork Repository**: Create your own fork of the project
3. **💬 Join Community**: Connect with other contributors
4. **📖 Read Documentation**: Familiarize yourself with the codebase

## 💻 Development Setup

### Local Development

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/google-account-creator.git
cd google-account-creator

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Install pre-commit hooks
pre-commit install

# 5. Set up environment
cp .env.example .env
# Edit .env with your configuration

# 6. Initialize configuration
python -c "
from core.configuration_manager import ConfigurationManager
config = ConfigurationManager()
config.initialize_default_config()
print('Development environment ready!')
"
```

### Docker Development

```bash
# Quick setup with Docker
./scripts/docker_setup.sh dev

# Or build and run manually
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

### IDE Configuration

#### VS Code Setup

```json
// .vscode/settings.json
{
    "python.defaultInterpreter": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false
}
```

#### PyCharm Setup

1. Set Python interpreter to `./venv/bin/python`
2. Enable Black formatter
3. Configure flake8 and mypy as external tools
4. Set pytest as default test runner

## 🏗️ Development Workflow

### Branch Strategy

We follow a **Git Flow** inspired workflow:

- **`main`**: Production-ready code
- **`develop`**: Integration branch for features
- **`feature/`**: Individual feature development
- **`bugfix/`**: Bug fixes
- **`hotfix/`**: Critical production fixes
- **`release/`**: Release preparation

### Workflow Steps

1. **Create Feature Branch**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Development Process**
   ```bash
   # Make your changes
   # Add tests
   # Update documentation
   
   # Commit with conventional commits
   git add .
   git commit -m "feat(core): add advanced memory optimization"
   ```

3. **Pre-submission Checks**
   ```bash
   # Run tests
   pytest tests/
   
   # Check code style
   black --check .
   flake8 .
   mypy .
   
   # Run performance tests
   python scripts/test_performance_profiler.py
   ```

4. **Submit Pull Request**
   ```bash
   git push origin feature/your-feature-name
   # Create PR via GitHub interface
   ```

### Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding/modifying tests
- `build`: Build system changes
- `ci`: CI configuration changes

**Examples:**
```bash
feat(adb): implement command caching for 40% speed improvement
fix(memory): resolve memory leak in optimization module
docs(api): add comprehensive endpoint documentation
perf(async): optimize task scheduling for 15x performance gain
```

## 📝 Coding Standards

### Python Style Guide

We follow **PEP 8** with some modifications:

- **Line Length**: 88 characters (Black default)
- **Indentation**: 4 spaces
- **Quotes**: Use double quotes for strings
- **Imports**: Group imports (standard, third-party, local)

### Code Structure

```python
"""
Module docstring explaining purpose and usage.

This module provides functionality for...
"""

import asyncio
import typing
from pathlib import Path

import aiofiles
import numpy as np

from core.logger import get_logger
from core.configuration_manager import ConfigurationManager

logger = get_logger(__name__)


class ExampleClass:
    """Class docstring with Korean comments for complex logic.
    
    이 클래스는 성능 최적화를 위한 핵심 기능을 제공합니다.
    """
    
    def __init__(self, config: ConfigurationManager) -> None:
        """Initialize with configuration."""
        self.config = config
        self._cache: Dict[str, Any] = {}
    
    async def process_data(
        self, 
        data: List[str], 
        *, 
        optimize: bool = True
    ) -> ProcessResult:
        """Process data with optional optimization.
        
        Args:
            data: Input data to process
            optimize: Whether to apply optimizations
            
        Returns:
            ProcessResult with timing and success metrics
            
        Raises:
            ProcessingError: If data processing fails
        """
        # 성능 최적화를 위한 캐싱 로직
        cache_key = self._generate_cache_key(data)
        if optimize and cache_key in self._cache:
            return self._cache[cache_key]
        
        result = await self._process_internal(data)
        
        if optimize:
            self._cache[cache_key] = result
            
        return result
```

### Documentation Standards

- **Docstrings**: Use Google-style docstrings
- **Type Hints**: Always include type hints
- **Korean Comments**: Use Korean for complex algorithm explanations
- **Examples**: Include usage examples in docstrings

### Error Handling

```python
# ✅ Good: Specific exception handling
try:
    result = await device.execute_command(command)
except ADBConnectionError as e:
    logger.error(f"ADB connection failed: {e}")
    raise DeviceError(f"Failed to execute command: {command}") from e
except TimeoutError as e:
    logger.warning(f"Command timeout: {command}")
    return None

# ❌ Bad: Catching all exceptions
try:
    result = await device.execute_command(command)
except Exception as e:
    return None
```

### Performance Considerations

- **Async/Await**: Use async patterns for I/O operations
- **Memory Management**: Implement proper cleanup
- **Caching**: Use appropriate caching strategies
- **Profiling**: Include performance measurements

```python
# Performance-conscious code example
class PerformantProcessor:
    """Processor with built-in performance optimizations."""
    
    def __init__(self):
        self._cache = LRUCache(maxsize=1000)
        self._memory_tracker = MemoryTracker()
    
    @performance_timer
    async def process_batch(self, items: List[Item]) -> List[Result]:
        """Process items in optimized batches."""
        # 메모리 사용량 모니터링
        with self._memory_tracker.track():
            # 배치 크기 최적화
            batch_size = self._calculate_optimal_batch_size()
            
            results = []
            for batch in chunked(items, batch_size):
                batch_results = await asyncio.gather(
                    *[self._process_item(item) for item in batch]
                )
                results.extend(batch_results)
                
                # 중간 정리 (메모리 누수 방지)
                if len(results) % 1000 == 0:
                    gc.collect()
            
            return results
```

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/                    # Unit tests
│   ├── test_adb_controller.py
│   ├── test_memory_optimizer.py
│   └── test_async_operations.py
├── integration/             # Integration tests
│   ├── test_account_creation.py
│   └── test_device_management.py
├── performance/             # Performance tests
│   ├── test_optimization.py
│   └── test_load.py
└── fixtures/               # Test fixtures
    ├── mock_devices.py
    └── sample_data.py
```

### Writing Tests

#### Unit Tests

```python
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from core.adb_controller import ADBController
from core.exceptions import ADBConnectionError


class TestADBController:
    """Test suite for ADB controller functionality."""
    
    @pytest.fixture
    async def adb_controller(self):
        """Fixture providing configured ADB controller."""
        controller = ADBController()
        await controller.initialize()
        yield controller
        await controller.cleanup()
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, adb_controller):
        """Test successful command execution."""
        # Given
        command = "shell getprop ro.build.version.release"
        expected_result = "11"
        
        # When
        result = await adb_controller.execute_command(command)
        
        # Then
        assert result.exit_code == 0
        assert expected_result in result.output
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, adb_controller):
        """Test command timeout handling."""
        # Given
        command = "shell sleep 10"
        timeout = 1
        
        # When/Then
        with pytest.raises(TimeoutError):
            await adb_controller.execute_command(command, timeout=timeout)
```

#### Performance Tests

```python
import time
import pytest
from core.performance_profiler import SystemProfiler


class TestPerformanceOptimizations:
    """Test performance optimization effectiveness."""
    
    @pytest.mark.performance
    async def test_memory_optimization_effectiveness(self):
        """Verify memory optimization reduces usage by 30%+."""
        # Baseline measurement
        baseline_memory = await self._measure_memory_usage()
        
        # Apply optimization
        optimizer = MemoryOptimizer()
        await optimizer.optimize()
        
        # Optimized measurement
        optimized_memory = await self._measure_memory_usage()
        
        # Verify improvement
        improvement = (baseline_memory - optimized_memory) / baseline_memory
        assert improvement >= 0.30, f"Memory improvement {improvement:.2%} < 30%"
    
    @pytest.mark.performance
    async def test_adb_optimization_speed(self):
        """Verify ADB optimization improves speed by 40%+."""
        # Test with and without optimization
        baseline_time = await self._measure_adb_performance(optimize=False)
        optimized_time = await self._measure_adb_performance(optimize=True)
        
        # Verify improvement
        improvement = (baseline_time - optimized_time) / baseline_time
        assert improvement >= 0.40, f"ADB improvement {improvement:.2%} < 40%"
```

### Test Coverage

- **Minimum Coverage**: 90% for new code
- **Critical Paths**: 100% coverage for optimization modules
- **Performance Tests**: Required for all optimization features

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Performance tests
pytest tests/performance/ -v --benchmark

# Coverage report
pytest --cov=core --cov-report=html

# Specific test
pytest tests/unit/test_adb_controller.py::TestADBController::test_execute_command_success -v
```

## 📚 Documentation

### Documentation Requirements

All contributions must include:

1. **Code Documentation**: Docstrings for all public APIs
2. **README Updates**: For new features or breaking changes
3. **API Documentation**: For new endpoints or data models
4. **Performance Documentation**: For optimization features

### Documentation Standards

#### API Documentation

```python
async def create_account(
    device_id: str,
    *,
    vpn_location: str = "US",
    verification_method: str = "sms",
    options: Optional[Dict[str, Any]] = None
) -> Account:
    """Create a new Google account with specified parameters.
    
    이 함수는 지정된 디바이스에서 Google 계정을 생성합니다.
    VPN 설정, SMS 인증 등 모든 단계를 자동화합니다.
    
    Args:
        device_id: Target Android device identifier
        vpn_location: VPN server location (default: "US")
        verification_method: Verification method ("sms", "email", "voice")
        options: Additional creation options
        
    Returns:
        Account: Created account with credentials and metadata
        
    Raises:
        DeviceNotFoundError: If device_id doesn't exist
        AccountCreationError: If account creation fails
        SMSVerificationError: If SMS verification fails
        
    Example:
        ```python
        account = await create_account(
            device_id="device_001",
            vpn_location="US",
            verification_method="sms"
        )
        print(f"Created account: {account.email}")
        ```
        
    Performance:
        - Average creation time: 3-5 minutes
        - Success rate: 90%+ with optimization
        - Memory usage: ~50MB per account
    """
```

#### Performance Documentation

```python
class ADBPerformanceOptimizer:
    """ADB communication performance optimizer.
    
    성능 최적화 결과:
    - 명령 실행 속도: 40-60% 향상
    - 캐시 적중률: 85-95%
    - 메모리 사용량: 20% 감소
    - 동시 연결 처리: 3배 증가
    
    Optimization Techniques:
        1. Command Caching: TTL-based cache with LRU eviction
        2. Command Fusion: Combine compatible operations
        3. Connection Pooling: Reuse ADB connections
        4. Parallel Execution: Concurrent command processing
        
    Benchmark Results:
        - Before: 250ms average command time
        - After: 100ms average command time
        - Improvement: 60% faster execution
    """
```

## 🔍 Code Review Process

### Review Checklist

#### Functionality
- [ ] Code works as intended
- [ ] Edge cases are handled
- [ ] Error handling is appropriate
- [ ] Performance considerations are addressed

#### Code Quality
- [ ] Follows coding standards
- [ ] Includes appropriate tests
- [ ] Documentation is complete
- [ ] No code smells or anti-patterns

#### Performance
- [ ] Optimization claims are verified
- [ ] Memory usage is reasonable
- [ ] No performance regressions
- [ ] Benchmarks are included (if applicable)

#### Security
- [ ] No security vulnerabilities
- [ ] Credentials are properly handled
- [ ] Input validation is present
- [ ] Sensitive data is protected

### Review Guidelines

#### For Authors

1. **Self-Review**: Review your own code first
2. **Small PRs**: Keep pull requests focused and small
3. **Clear Description**: Explain what and why
4. **Include Tests**: Add comprehensive tests
5. **Performance Data**: Include benchmarks for optimizations

#### For Reviewers

1. **Be Constructive**: Provide helpful feedback
2. **Ask Questions**: Clarify unclear code
3. **Suggest Improvements**: Offer better alternatives
4. **Test Locally**: Verify functionality when needed
5. **Check Performance**: Validate optimization claims

### PR Template

```markdown
## 📝 Description

Brief description of changes and motivation.

## 🎯 Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Performance improvement
- [ ] Documentation update

## 🧪 Testing

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Performance tests added/updated
- [ ] Manual testing completed

## 📊 Performance Impact

- [ ] No performance impact
- [ ] Performance improvement (include benchmarks)
- [ ] Potential performance impact (explain)

### Benchmarks (if applicable)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Speed  | 250ms  | 100ms | 60% faster |
| Memory | 100MB  | 70MB  | 30% less   |

## 📋 Checklist

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Code is commented (especially complex logic)
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] Performance benchmarks included (if applicable)
```

## 🐛 Bug Reports

### Bug Report Template

```markdown
## 🐛 Bug Description

A clear and concise description of what the bug is.

## 🔄 Reproduction Steps

Steps to reproduce the behavior:
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

## 🎯 Expected Behavior

A clear description of what you expected to happen.

## 📱 Environment

- OS: [e.g. macOS 12.0, Ubuntu 20.04]
- Python Version: [e.g. 3.10.0]
- Project Version: [e.g. 1.2.0]
- Device Model: [e.g. Samsung Galaxy S21]
- Android Version: [e.g. 11]

## 📋 Additional Context

- Error logs
- Screenshots
- Performance impact
- Frequency of occurrence
```

### Bug Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| **Critical** | System crash, data loss | 24 hours |
| **High** | Major feature broken | 48 hours |
| **Medium** | Minor feature issue | 1 week |
| **Low** | Cosmetic, enhancement | 2 weeks |

## ✨ Feature Requests

### Feature Request Template

```markdown
## 💡 Feature Description

A clear and concise description of the feature you'd like to see.

## 🎯 Problem Statement

What problem does this feature solve? Who would benefit from it?

## 💭 Proposed Solution

Describe your proposed solution in detail.

## 🔄 Alternative Solutions

Describe any alternative solutions or features you've considered.

## 📊 Impact Assessment

- Performance impact
- Complexity level
- Maintenance overhead
- User benefit

## 🎨 Mockups/Examples

Include any mockups, diagrams, or code examples.
```

### Feature Evaluation Criteria

- **User Value**: How much value does this provide?
- **Implementation Effort**: How complex is the implementation?
- **Maintenance Cost**: Ongoing maintenance requirements
- **Performance Impact**: Effect on system performance
- **Security Implications**: Security considerations

## 🏆 Recognition

### Contributor Recognition

We recognize contributions through:

- **Contributor List**: All contributors listed in README
- **Release Notes**: Major contributions highlighted
- **Special Mentions**: Outstanding contributions recognized
- **Expert Status**: Technical expertise recognition

### Contribution Types

- **Code Contributions**: Features, bug fixes, optimizations
- **Documentation**: Guides, tutorials, API docs
- **Testing**: Test suites, performance benchmarks
- **Community**: Support, mentoring, issue triaging
- **Design**: UI/UX improvements, diagrams

### Hall of Fame

Contributors with significant impact:

- **Performance Champions**: Major optimization contributions
- **Quality Guardians**: Testing and code quality improvements
- **Documentation Heroes**: Comprehensive documentation
- **Community Leaders**: Outstanding community support

## ❓ Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Q&A and general discussions
- **Discord Server**: Real-time chat and support
- **Email**: Direct contact for sensitive issues

### Documentation Resources

- **API Documentation**: Complete API reference
- **Architecture Guide**: System design and components
- **Performance Guide**: Optimization techniques
- **Troubleshooting**: Common issues and solutions

### Mentorship Program

New contributors can request mentorship:

1. **Comment on Issues**: Express interest in contributing
2. **Join Discord**: Connect with mentors
3. **Pair Programming**: Schedule pairing sessions
4. **Code Reviews**: Get detailed feedback

### Common Questions

**Q: How do I set up the development environment?**
A: Follow the [Development Setup](#-development-setup) section.

**Q: What should I work on as a first contribution?**
A: Look for issues labeled `good-first-issue` or `help-wanted`.

**Q: How do I run performance tests?**
A: Use `pytest tests/performance/ -v --benchmark`.

**Q: Where can I find Korean-speaking contributors?**
A: Join our Discord server and check the #korean channel.

**Q: How do I optimize performance in my contribution?**
A: Review our [Performance Guide](docs/performance.md) and existing optimization examples.

---

## 📜 Code of Conduct

### Our Standards

- **Be Respectful**: Treat everyone with respect and kindness
- **Be Inclusive**: Welcome people of all backgrounds and skill levels
- **Be Constructive**: Provide helpful and actionable feedback
- **Be Patient**: Help others learn and grow
- **Be Professional**: Maintain professional standards

### Unacceptable Behavior

- Harassment, discrimination, or offensive language
- Personal attacks or trolling
- Spam or off-topic content
- Sharing private information without consent
- Any form of abuse or intimidation

### Enforcement

Community leaders will enforce these standards and may:

- Remove inappropriate content
- Temporarily or permanently ban violators
- Report serious violations to appropriate authorities

---

## 🙏 Thank You

Thank you for contributing to Google Account Creator! Your efforts help make this project better for everyone. Whether you're fixing bugs, adding features, improving documentation, or helping other contributors, your work is valued and appreciated.

Together, we're building a powerful, optimized, and reliable system for automated account creation. Every contribution, no matter how small, makes a difference.

**Happy Contributing! 🚀**

---

<div align="center">

**🔗 [Back to Main Documentation](README.md)**

</div> 