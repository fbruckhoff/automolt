---
includes: Data models, persistence layer, file operations, and data validation
excludes: Specific API client implementations
related: client-configuration.md, session-targeting-design.md, ../../ARCHITECTURE.md
---

# Models and Persistence

## Models

Models provide data validation, serialization, and type safety for the application.

### Location and Structure

- Models reside under `models/`
- Each model represents a specific data structure with validation rules

### Responsibilities

1. **Data Validation**
   - Enforce data integrity (e.g., email format, required fields)
   - Implemented using Pydantic

2. **Serialization**
   - Handle conversion between JSON strings (for API/Disk) and Python Objects (for Logic)
   - Provide consistent data representation across the application

3. **Type Safety**
   - Provide a single source of truth for data structures
   - Enable IDE autocompletion and static analysis
   - Protect the application from bad data

## Persistence Layer

The persistence layer handles file operations and data storage.

### Location and Structure

- Persistence files reside under `persistence/`
- Each persistence module is responsible for a specific data storage concern

### Agent Configuration

- Handles `agent.json` file operations
- Files live in `.agents/` subdirectories as runtime data
- Each agent has a subdirectory in `.agents/` matching its username (handle)
- `agent.json` files are mapped to `AgentConfig` objects

### Directory Structure

- `.agents/`: Folder where all agents are stored as sub-folders with the agent's name as folder name
- `.sessions/`: Folder where per-terminal-session state is stored as `<PPID>.json` files

### Responsibilities

- Read and write configuration files
- Map JSON data to and from model objects
- Maintain data integrity
- Handle file system operations
