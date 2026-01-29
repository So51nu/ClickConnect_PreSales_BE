# salelead/gsheets.py
import gspread
from django.conf import settings

def fetch_google_sheet_rows():
    """
    Return rows from Google Sheet as list of dicts.
    Abhi ke liye empty list -> koi opportunity sync nahi karega.
    """
    return []
