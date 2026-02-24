---
glob: "*.py"
---

When writing or modifying Python code, follow these requirements:

## Code Quality & Style
- Follow PEP 8 style guidelines with these specifics:
  - Use 4-space indentation (never tabs)
  - Naming: snake_case for functions/variables/modules, PascalCase for classes, UPPER_CASE for constants
  - Two blank lines between top-level definitions, one blank line between methods
- Use type hints for all function signatures (parameters and return values)
  - Import from `typing` for Python <3.9, use built-in generics for Python ≥3.9 (`list[str]` instead of `List[str]`)
  - Use `Optional[T]` or `T | None` for nullable types
  - For complex types, consider using `TypeAlias` or `TypedDict`
- Write self-documenting code:
  - Use descriptive variable/function names that reveal intent
  - Avoid abbreviations unless universally understood (e.g., `num`, `ctx`, `idx`)
  - Single letters acceptable only for: common iterators (`i`, `j`, `k`), comprehensions, mathematical formulas, or well-established conventions (`f` for file handles)
- Add docstrings using Google or NumPy style:
  - Required: all public modules, classes, and functions
  - Include: brief description, Args, Returns, Raises (if applicable)
  - Optional but recommended: Examples for complex functions
- Keep functions focused and concise:
  - Target: <20 lines per function
  - If longer, extract helper functions or refactor
  - Each function should do one thing well

## Architecture & Separation of Concerns
- Apply layered architecture:
  - Separate data access (repositories/DAOs), business logic (services), and presentation (views/controllers/CLI)
  - Never mix concerns: no SQL in UI code, no UI logic in models
- File organization:
  - One public class per file (exception: tightly coupled helper classes, dataclasses, or enums)
  - Group related functionality in modules/packages
  - Use `__init__.py` to define public APIs
- Avoid global state:
  - Use dependency injection instead of singletons or globals
  - Pass dependencies explicitly through constructors or function parameters
  - For application-wide state, use dependency injection containers or context managers
- Configuration management:
  - Extract all configuration to separate files (e.g. `config.py`, `.env`, YAML/JSON/TOML files)
  - Use environment variables for deployment-specific settings
  - Never hardcode: credentials, API keys, URLs, file paths, magic numbers
  - Use constants with descriptive names for "magic" values
- Follow SOLID principles:
  - Single Responsibility: Each class/function has one reason to change
  - Open/Closed: Extend behavior via inheritance/composition, not modification
  - Liskov Substitution: Subtypes must be substitutable for base types
  - Interface Segregation: Many specific interfaces > one general interface
  - Dependency Inversion: Depend on abstractions, not concretions

## Error Handling & Robustness
- Exception handling best practices:
  - Use specific exception types (e.g., `FileNotFoundError`, `ValueError`)
  - Never use bare `except:` — catch specific exceptions or use `except Exception:` with justification
  - Create custom exceptions for domain-specific errors
  - Include error context in exception messages
  - Re-raise exceptions with `raise ... from` to preserve stack traces
- Resource management:
  - Always use context managers (`with` statements) for: files, database connections, locks, network sockets
  - Implement `__enter__` and `__exit__` for custom resources
  - Use `contextlib` for simple context managers
- Input validation:
  - Validate at system boundaries (API endpoints, CLI entry points, public function interfaces)
  - Fail fast with clear, actionable error messages
  - Use assertions for internal invariants, not input validation
  - Use Pydantic where possible
- Logging:
  - Use the `logging` module for applications and libraries; `print()` is acceptable for simple scripts, CLI output, or temporary debugging
  - Include context in log messages (e.g. user ID, request ID, operation being performed)
  - Use appropriate log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Configure logging at application entry point, not in libraries

## Performance & Best Practices
- Pythonic idioms:
  - Use comprehensions for transformations: `[x*2 for x in items]` instead of loops
  - Use dict/set comprehensions: `{k: v for k, v in pairs}`
  - Use generator expressions for large datasets: `(x*2 for x in huge_list)`
- Standard library first:
  - Prefer built-in functions: `any()`, `all()`, `sum()`, `map()`, `filter()`
  - Use `collections`: `defaultdict`, `Counter`, `deque`, `namedtuple`
  - Use `itertools` for iteration patterns: `groupby()`, `chain()`, `combinations()`
  - Use `functools`: `lru_cache`, `partial`, `reduce`
- Memory efficiency:
  - Use generators for large datasets or infinite sequences
  - Prefer iteration over loading entire datasets into memory
  - Use `__slots__` for classes with many instances

## Security
- Never execute untrusted code:
  - Never run `eval()` or `exec()` on any external input
  - If dynamic code execution is required, use `ast.literal_eval()` for safe data structures
- Database security:
  - Always use parameterized queries/prepared statements
  - Never build SQL with string concatenation or f-strings
  - Use ORMs or query builders
- Input sanitization:
  - Validate and sanitize all external inputs (user input, API data, file contents)
  - Use allowlists over denylists
  - Escape output appropriate to context (HTML, SQL, shell)
- Secrets management:
  - Never log sensitive data like passwords, credentials, API keys, tokens, PII, etc.
  - Use environment variables or secret management services
  - Scrub secrets from error messages and stack traces
- Additional considerations:
  - Use `secrets` module for cryptographic randomness (not `random`)
  - Validate file paths to prevent directory traversal attacks
  - Set appropriate file permissions for sensitive data

## Imports & Dependencies
- Imports:
  1. Standard library imports
  2. Related third-party imports
  3. Local application/library imports
  - Separate each group with a blank line
  - Sort alphabetically within each group (Ruff will enforce this)
- Import practices:
  - Use absolute imports for clarity
  - Avoid wildcard imports (`from module import *`)
  - Import only what you need; remove unused imports
  - Use `from module import specific_item` for frequently used items
  - Use `import module` for namespacing when there might be name conflicts
- Conditional imports:
  - Place at module level when possible
  - Use runtime imports only for optional dependencies or avoiding circular imports
  - Document why conditional imports are necessary

## Refactoring Guidelines
- When refactoring existing code:
  - Preserve functionality: ensure tests pass before and after
  - For larger refactoring tasks, break them down into smaller, focused changes and ask for consent before doing any refactoring
  - Recommend to add tests before refactoring if coverage is lacking
  - Fix violations systematically, not all at once
  - Document breaking changes in comments or migration guides
- Identify anti-patterns:
  - God objects → split into focused classes
  - Long functions → extract methods
  - Duplicated code → extract to shared functions/classes
  - Hardcoded values → extract to configuration/constants
  - Complex conditions → extract to well-named predicates
  - Deprecated features:
    - Use `pathlib` instead of `os.path`
    - Use f-strings instead of `%` or `.format()`
    - Use `subprocess` instead of `os.system()`

## Testing & Maintainability
- Write testable code:
  - Limit nesting depth (max 3-4 levels)
  - Keep cyclomatic complexity low (<10 per function, ideally <5)
  - Minimize dependencies; make them explicit and injectable
  - Favor pure functions (same input → same output, no side effects)
- Dependency management:
  - Make dependencies explicit in function signatures or constructors
  - Use protocols/abstract base classes for interface definitions
  - Depend on abstractions rather than concrete implementations to allow flexibility
- Code organization:
  - Separate I/O and side effects from business logic
  - Use the Repository pattern for data access
  - Extract impure operations to boundaries
  - Design code so logic can be tested independently of external dependencies
