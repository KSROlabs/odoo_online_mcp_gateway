#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convenience entrypoint for MCP clients (Claude Desktop / Cursor) that run a local command.

This avoids requiring a pip install. Example:
  python3 /path/to/odoo_online_mcp_gateway/run_gateway.py stdio
"""
import os
import sys


def _add_project_to_path():
    here = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, here)


def main():
    _add_project_to_path()
    from odoo_online_mcp_gateway.cli import main as cli_main  # noqa: E402

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

