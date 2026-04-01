from database.db import get_connection
from polling import start_polling


def main():
    get_connection()
    start_polling()


if __name__ == "__main__":
    main()