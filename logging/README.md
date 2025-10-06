# OpChat Backend Configuration

## Logging Configuration

The application uses YAML-based logging configuration with environment-specific settings.

### Configuration Files

- `logging.yaml` - Default/base logging configuration
- `logging.development.yaml` - Development environment (verbose, includes DEBUG)
- `logging.production.yaml` - Production environment (minimal console output, comprehensive file logging)

### Environment Selection

The logging system automatically selects the appropriate configuration based on the `ENVIRONMENT` environment variable:

```bash
ENVIRONMENT=development  # Uses logging.development.yaml
ENVIRONMENT=production   # Uses logging.production.yaml  
ENVIRONMENT=test         # Falls back to logging.yaml
```

### Log Files

All log files are created in the `logs/` directory:

- `opchat.log` - General application logs (INFO and above)
- `opchat_error.log` - Error logs only
- `opchat_debug.log` - Debug logs (development only)

### Log Levels by Environment

**Development:**
- Console: DEBUG level with standard formatting
- Files: DEBUG level with detailed formatting including line numbers
- SQLAlchemy: Shows SQL queries

**Production:**
- Console: WARNING level only (for errors)
- Files: INFO level with rotation (50MB, 10 backups)
- Syslog: ERROR level for monitoring systems
- SQLAlchemy: ERROR level only

### Usage in Code

```python
from app.core.logging.logging import get_logger

logger = get_logger(__name__)
logger.info("This is an info message")
logger.error("This is an error message")
```

### Manual Configuration Override

You can override the configuration file using the `LOG_CFG` environment variable:

```bash
LOG_CFG=/path/to/custom/logging.yaml python app/main.py
```

### Log Rotation

Production logs use rotating file handlers:
- Maximum file size: 50MB
- Backup count: 10 files
- Total log storage: ~500MB per log type
