from abc import ABC, abstractmethod
from typing import List
class FileReader(ABC):
    @abstractmethod
    def extract_text(self, file_path, **kwargs) -> List[str]:
        pass

class FileWriter(ABC):
    @abstractmethod
    def write_text(self, file_path, texts, **kwargs) -> bool:
        pass

class ExcelFileReader(FileReader):
    def extract_text(self, file_path, start_row, end_row, target_column) -> List[str]:
        from openpyxl import load_workbook
        workbook = load_workbook(file_path)
        sheet = workbook.active  # Assuming we are working with the active sheet
        texts = []

        for row in range(start_row, end_row + 1):
            cell_value = sheet.cell(row=row, column=target_column).value
            if cell_value is not None:
                texts.append(str(cell_value))
        return texts