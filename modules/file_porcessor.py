from abc import ABC, abstractmethod
from typing import List
class FileReader(ABC):
    @abstractmethod
    def extract_text(self, file_path, **kwargs) -> List[str]:
        pass