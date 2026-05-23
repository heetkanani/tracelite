# tracelite

Open-source observability SDK for LLM apps. Local-first, lightweight.

```python
from tracelite import init, observe

init(api_key="your-api-key")

@observe()
def ask(question):
    ...
```

> Under active development. Not ready for production.