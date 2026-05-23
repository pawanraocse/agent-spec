# Speculative Features Anti-Pattern

> **Building features nobody asked for is not initiative — it's waste. Every unrequested feature is code that must be tested, maintained, and understood.**

LLMs frequently add "helpful" extras: additional export formats, configuration options, notification hooks, and extensibility points. These feel productive but create maintenance burden and obscure the actual requirement.

---

## Example 1: Unrequested Export Formats

**User request:** *"Export data as JSON"*

### ❌ What LLMs Do (Speculative)

**Python:**
```python
import json
import csv
import xml.etree.ElementTree as ET
from enum import Enum

class ExportFormat(Enum):
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    YAML = "yaml"

class DataExporter:
    def __init__(self, data: list[dict]):
        self.data = data
    
    def export(self, format: ExportFormat, filepath: str) -> str:
        exporters = {
            ExportFormat.JSON: self._export_json,
            ExportFormat.CSV: self._export_csv,
            ExportFormat.XML: self._export_xml,
            ExportFormat.YAML: self._export_yaml,
        }
        return exporters[format](filepath)
    
    def _export_json(self, filepath: str) -> str:
        with open(filepath, 'w') as f:
            json.dump(self.data, f, indent=2)
        return filepath
    
    def _export_csv(self, filepath: str) -> str:
        # ... 20 more lines
        pass
    
    def _export_xml(self, filepath: str) -> str:
        # ... 30 more lines
        pass
    
    def _export_yaml(self, filepath: str) -> str:
        # ... 15 more lines
        pass
```

**Problems:**
- User asked for JSON. Got JSON + CSV + XML + YAML.
- 4x the code to test and maintain.
- YAML export requires a new dependency (`pyyaml`).
- The Enum/dispatch pattern is overkill for one format.

### ✅ What Should Happen (Simple)

**Python:**
```python
import json

def export_as_json(data: list[dict], filepath: str) -> str:
    """Export data as JSON to the specified file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    return filepath
```

**Java:**
```java
public String exportAsJson(List<Map<String, Object>> data, String filepath) 
        throws IOException {
    objectMapper.writerWithDefaultPrettyPrinter()
                .writeValue(new File(filepath), data);
    return filepath;
}
```

If CSV/XML/YAML are needed later, the user will ask. Add them then.

---

## Example 2: Premature Configurability

**User request:** *"Add logging to the service"*

### ❌ What LLMs Do (Over-Configured)

**Python:**
```python
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

@dataclass
class LogConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[Path] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_output: bool = True
    json_format: bool = False

class LoggerFactory:
    _loggers: dict = {}
    
    @classmethod
    def create_logger(cls, name: str, config: Optional[LogConfig] = None) -> logging.Logger:
        if name in cls._loggers:
            return cls._loggers[name]
        
        config = config or LogConfig()
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, config.level))
        
        formatter = logging.Formatter(config.format)
        
        if config.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        if config.file_path:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                config.file_path,
                maxBytes=config.max_file_size,
                backupCount=config.backup_count
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger
```

**Problems:**
- User asked for "logging." Got a logging framework.
- LogConfig with 8 options nobody will use.
- Factory pattern with singleton caching.
- File rotation, JSON format, backup count — all speculative.

### ✅ What Should Happen (Simple)

**Python:**
```python
import logging

logger = logging.getLogger(__name__)

# In the service method:
logger.info("Processing order %s", order_id)
```

**Java:**
```java
private static final Logger logger = LoggerFactory.getLogger(OrderService.class);

// In the service method:
logger.info("Processing order {}", orderId);
```

Standard library logging with sensible defaults. If rotation or custom formatting is needed, the user will configure it.

---

> **Key Takeaway:** Every feature you add that wasn't requested is a feature that must be tested, documented, and maintained. "Just in case" code is never free — it has a carrying cost forever. Build what was asked. Stop there.

---

*Part of the agent-spec Simplicity First standard. See `coding-standards/SIMPLICITY-FIRST.md`.*
