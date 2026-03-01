"""Entry point for finance_tui."""

from finance_tui.app import FinanceTUI


def main():
    app = FinanceTUI()
    app.run()


if __name__ == "__main__":
    main()
