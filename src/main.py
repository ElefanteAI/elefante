import sys

def main():
    if "--mcp" in sys.argv or "stdio" in sys.argv:
        from src.mcp.server import main as mcp_main
        sys.exit(mcp_main())
    else:
        from src.desktop import run_gui
        sys.exit(run_gui())

if __name__ == "__main__":
    main()
