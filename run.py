#!/usr/bin/env python3
"""
BBagent 一键启动脚本
用法: python run.py
"""
import sys
import uvicorn


def main():
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["backend"],
    )


if __name__ == "__main__":
    main()
