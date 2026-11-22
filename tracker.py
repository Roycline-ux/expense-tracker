import json
import os
from datetime import date

DATA_FILE = "expenses.json"

expenses = []


def load_expenses():
    global expenses
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r") as f:
            expenses = json.load(f)
    except (json.JSONDecodeError, OSError):
        print("Could not read saved data. Starting fresh.")
        expenses = []


def save_expenses():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(expenses, f, indent=2)
    except OSError:
        print("Warning: could not save your data.")


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

    category = input("Category (e.g. food, transport): ").strip().lower()
    description = input("Description: ").strip()

    expense = {
        "amount": amount,
        "category": category or "other",
        "description": description,
        "date": str(date.today()),
    }
    expenses.append(expense)
    save_expenses()
    print("Expense added and saved!")


def view_expenses():
    print("\n--- All Expenses ---")
    if not expenses:
        print("No expenses yet.")
        return

    for i, e in enumerate(expenses, start=1):
        print(f"{i}. {e['date']} | {e['category']:<10} | {e['amount']:>8.2f} | {e['description']}")


def view_summary():
    print("\n--- Summary ---")
    if not expenses:
        print("No expenses to summarize.")
        return

    total = sum(e["amount"] for e in expenses)
    print(f"Total spent: {total:.2f}")
    print(f"Number of expenses: {len(expenses)}")

    category_totals = {}
    for e in expenses:
        cat = e["category"]
        category_totals[cat] = category_totals.get(cat, 0) + e["amount"]

    print("\nBy category:")
    for cat, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True):
        percent = (amount / total) * 100
        print(f"  {cat:<10} {amount:>8.2f}  ({percent:.1f}%)")


def delete_expense():
    print("\n--- Delete Expense ---")
    if not expenses:
        print("No expenses to delete.")
        return

    view_expenses()

    choice = input("\nEnter the number to delete (or press Enter to cancel): ").strip()
    if choice == "":
        print("Cancelled.")
        return

    if not choice.isdigit():
        print("Please enter a valid number.")
        return

    index = int(choice) - 1
    if index < 0 or index >= len(expenses):
        print("That number is not in the list.")
        return

    e = expenses[index]
    confirm = input(f"Delete '{e['description']}' ({e['amount']:.2f})? (y/n): ").strip().lower()
    if confirm == "y":
        expenses.pop(index)
        save_expenses()
        print("Expense deleted.")
    else:
        print("Cancelled.")


def main():
    load_expenses()

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