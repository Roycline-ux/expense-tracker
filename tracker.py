from datetime import date

expenses = []


def show_menu():
    print("\n=== Expense Tracker ===")
    print("1. Add expense")
    print("2. View expenses")
    print("3. View summary")
    print("4. Quit")


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
    print("Expense added!")


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


def main():
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
            print("Goodbye!")
            break
        else:
            print("Invalid choice, try again.")


if __name__ == "__main__":
    main()