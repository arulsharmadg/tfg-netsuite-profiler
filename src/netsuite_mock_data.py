from faker import Faker
import random

fake = Faker()

TABLES = {
    "CUSTOMER": 500,
    "VENDOR": 200,
    "ITEM": 1000,
    "TRANSACTION": 5000,
    "EMPLOYEE": 150,
    "ACCOUNT": 300,
    "SUBSIDIARY": 20,
    "DEPARTMENT": 50,
    "SALESORDER": 2500,
    "PURCHASEORDER": 800,
}


def generate_mock_row_counts():
    print(f"{'Table':<20} {'Row Count':>10}")
    print("-" * 32)
    for table, base_count in TABLES.items():
        row_count = base_count + random.randint(-50, 50)
        print(f"{table:<20} {row_count:>10,}")


if __name__ == "__main__":
    generate_mock_row_counts()
