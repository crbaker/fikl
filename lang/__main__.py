"""fsql entry point script."""
# lang/__main__.py

from lang import cli, __app_name__

def main():
    """
    Main application function that starts the FSQL CLI.
    """
    cli.app(prog_name=__app_name__)

if __name__ == "__main__":
    main()
