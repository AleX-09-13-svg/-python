from common.inventor_connection import get_inventor
from confirmat.confirmat import create_confirmat_features


def main():
    inv = get_inventor()
    created = create_confirmat_features(inv.ActiveDocument)
    print("Confirmat hole features created:", created)


if __name__ == "__main__":
    main()
