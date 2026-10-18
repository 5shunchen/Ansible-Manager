"""分页依赖：列表接口统一 ?page=&page_size= 查询参数。"""
from dataclasses import dataclass


@dataclass
class PageParams:
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def clamp(self, max_size: int = 100) -> "PageParams":
        self.page = max(1, self.page)
        self.page_size = min(max(1, self.page_size), max_size)
        return self
