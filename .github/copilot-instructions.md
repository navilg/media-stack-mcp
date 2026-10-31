# Copilot instructions

- Keep tool descriptions and instructions token-efficient without losing constraints, inputs, outputs, or error behavior.
- Present simple, flat JSON records as TSV (header row; tab-separated fields and rows). Join list values in a cell with commas. Use TOON for complex/nested JSON, preserving structure and values. Apply these formats to presented data, not protocol payloads or configuration files.
- Preserve the existing architecture: MCP registration and startup are in `server.py`; service integrations belong in their `media_stack/<service>.py` modules; shared configuration/constants/formatting belong in their existing modules.
- Keep tool inputs validated and errors explicit. Preserve established return conventions (TSV rows, `Empty list`, or an `Error:` string); set timeouts on network requests and handle request failures consistently.
- Keep credentials out of source, logs, and examples. Use environment variables and `test.env.example`; never expose or overwrite local secret files.
- Target Python 3.11+. Avoid adding dependencies unless needed; update `requirements.txt` when one is introduced.
- For behavior changes, add or update focused tests and run `python test_server.py`. `test_mcp_http.py` is for checking a running HTTP server.
- Update `README.md` when changing public MCP tools, arguments, output, configuration, or run instructions.
- Always keep the code simple. Use functions/method without class.
