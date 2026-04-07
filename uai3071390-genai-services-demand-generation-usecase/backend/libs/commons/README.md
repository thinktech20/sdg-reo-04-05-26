# sdg-commons

Shared backend library for common identity and logging utilities.

## ADO Ticket

- [584260 — Risk Assessment Agent Foundation Setup](https://dev.azure.com/vernova/PWRDT-DataScience%20AI/_workitems/edit/584260)

## Modules

| Module | Purpose |
|---|---|
| commons.identity | UserContext and identity structures |
| commons.logging | get_logger shim for consistent logger creation |
| commons.databricks | placeholder module |
| commons.middleware | shared auth middleware placeholder |

## Structure

```text
libs/commons/
├── pyproject.toml
├── src/commons/
│   ├── identity.py
│   ├── logging.py
│   ├── databricks.py
│   └── middleware/__init__.py
└── tests/
    ├── test_identity.py
    ├── test_logging.py
    └── test_databricks.py
```

## Tests

```bash
cd backend
uv run pytest libs/commons/
```
