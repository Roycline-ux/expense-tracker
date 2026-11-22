import sqlite3
from datetime import date

DB_FILE = "expenses.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL
            )
            """
        )


def show_menu():
    print("\n=== Expense Tracker ===")
    print("1. Add expense")
    print("2. View expenses")
    print("3. View summary")
    print("4. Delete expense")
    print("5. Quit")


def add_expense():
    print("\n--- Add Expense ---")

    while True:
        try:
            amount = float(input("Amount: "))
            if amount <= 0:
                print("Amount must be greater than zero.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")

    category = input("Category (e.g. food, transport): ").strip().lower() or "other"
    description = input("Description: ").strip()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO expenses (amount, category, description, date) VALUES (?, ?, ?, ?)",
            (amount, category, description, str(date.today())),
        )
    print("Expense added and saved!")


def view_expenses():
    print("\n--- All Expenses ---")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, date, category, amount, description FROM expenses ORDER BY date, id"
        ).fetchall()

    if not rows:
        print("No expenses yet.")
        return

    for row_id, d, category, amount, description in rows:
        print(f"{row_id}. {d} | {category:<10} | {amount:>8.2f} | {description}")


def view_summary():
    print("\n--- Summary ---")
    with get_connection() as conn:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses"
        ).fetchone()

        if count == 0:
            print("No expenses to summarize.")
            return

        print(f"Total spent: {total:.2f}")
        print(f"Number of expenses: {count}")

        rows = conn.execute(
            """
            SELECT category, SUM(amount) AS cat_total
            FROM expenses
            GROUP BY category
            ORDER BY cat_total DESC
            """
        ).fetchall()

    print("\nBy category:")
    for category, cat_total in rows:
        percent = (cat_total / total) * 100
        print(f"  {category:<10} {cat_total:>8.2f}  ({percent:.1f}%)")


def delete_expense():
    print("\n--- Delete Expense ---")
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    if count == 0:
        print("No expenses to delete.")
        return

    view_expenses()

    choice = input("\nEnter the ID to delete (or press Enter to cancel): ").strip()
    if choice == "":
        print("Cancelled.")
        return
    if not choice.isdigit():
        print("Please enter a valid number.")
        return

    expense_id = int(choice)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT description, amount FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()

        if row is None:
            print("That ID is not in the list.")
            return

        description, amount = row
        confirm = input(f"Delete '{description}' ({amount:.2f})? (y/n): ").strip().lower()
        if confirm == "y":
            conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            print("Expense deleted.")
        else:
            print("Cancelled.")


def main():
    init_db()

    while True:
        show_menu()
        choice = input("Choose an option: ").strip()

        if choice == "1":
            add_expense()
        elif choice == "2":
            view_expenses()
        elif choice == "3":
            view_summary()
        elif choice == "4":
            delete_expense()
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Invalid choice, try again.")


if __name__ == "__main__":
    main()