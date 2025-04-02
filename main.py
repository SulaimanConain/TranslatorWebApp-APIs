import flet as ft
from healthcare_translator_ui import HealthcareTranslatorUI

def main(page: ft.Page):
    app = HealthcareTranslatorUI(page)

# For web/desktop
if __name__ == '__main__':
    ft.app(target=main) 