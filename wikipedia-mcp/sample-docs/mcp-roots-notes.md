# MCP Roots notes

Roots let a client tell a server which directories it may work with.
Each root is a `file://` URI. Roots are not a sandbox: the server must
validate every path itself and refuse anything outside the shared roots.
