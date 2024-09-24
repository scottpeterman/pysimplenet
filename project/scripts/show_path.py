import sys
import click

@click.command()
@click.option('--arg1')
@click.option('--flag1', is_flag=True, help='A boolean flag')
def show_path(arg1, flag1):
    print(f"Using this python interpreter: {sys.executable}")
    print(f"Argument 1: {arg1}")
    print(f"Flag 1: {flag1}")

if __name__ == '__main__':
    show_path()
