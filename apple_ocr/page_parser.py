"""
页面范围解析模块

支持解析如下格式的页面范围：
- 单页：1, 5, 10
- 范围：1-5, 10-15, 100-200
- 混合：1,3,5-10,15,20-25
"""

import re
from typing import List, Set, Tuple


class PageRangeParser:
    """页面范围解析器"""

    @staticmethod
    def parse_page_ranges(page_spec: str, total_pages: int) -> List[int]:
        """
        解析页面范围字符串，返回页面索引列表（0-based）

        Args:
            page_spec: 页面范围字符串，如 "1,3,5-10,15"
            total_pages: PDF总页数

        Returns:
            页面索引列表（0-based），已排序去重

        Raises:
            ValueError: 页面范围格式错误或超出范围
        """
        if not page_spec or not page_spec.strip():
            return list(range(total_pages))  # 空字符串表示所有页面

        page_set: Set[int] = set()

        # 分割逗号分隔的部分
        parts = [part.strip() for part in page_spec.split(",")]

        for part in parts:
            if not part:
                continue

            if "-" in part:
                # 处理范围，如 "5-10"
                range_match = re.match(r"^(\d+)-(\d+)$", part)
                if not range_match:
                    raise ValueError(f"无效的页面范围格式: '{part}'")

                start_page = int(range_match.group(1))
                end_page = int(range_match.group(2))

                if start_page > end_page:
                    raise ValueError(
                        f"起始页面不能大于结束页面: {start_page}-{end_page}"
                    )

                # 验证页面范围
                PageRangeParser._validate_page_number(start_page, total_pages)
                PageRangeParser._validate_page_number(end_page, total_pages)

                # 添加范围内的所有页面（转换为0-based）
                for page in range(start_page - 1, end_page):
                    page_set.add(page)

            else:
                # 处理单页，如 "5"
                if not re.match(r"^\d+$", part):
                    raise ValueError(f"无效的页面号格式: '{part}'")

                page_num = int(part)
                PageRangeParser._validate_page_number(page_num, total_pages)

                # 转换为0-based索引
                page_set.add(page_num - 1)

        # 返回排序后的页面列表
        return sorted(list(page_set))

    @staticmethod
    def _validate_page_number(page_num: int, total_pages: int) -> None:
        """验证页面号是否有效"""
        if page_num < 1:
            raise ValueError(f"页面号必须大于0: {page_num}")
        if page_num > total_pages:
            raise ValueError(f"页面号超出范围: {page_num} > {total_pages}")

    @staticmethod
    def format_page_ranges(pages: List[int]) -> str:
        """
        将页面索引列表格式化为范围字符串（1-based）

        Args:
            pages: 页面索引列表（0-based）

        Returns:
            格式化的页面范围字符串
        """
        if not pages:
            return ""

        # 转换为1-based并排序
        pages_1based = sorted([p + 1 for p in pages])

        ranges = []
        start = pages_1based[0]
        end = start

        for page in pages_1based[1:]:
            if page == end + 1:
                # 连续页面，扩展范围
                end = page
            else:
                # 非连续，添加当前范围
                if start == end:
                    ranges.append(str(start))
                else:
                    ranges.append(f"{start}-{end}")
                start = end = page

        # 添加最后一个范围
        if start == end:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{end}")

        return ",".join(ranges)


def parse_pages(page_spec: str, total_pages: int) -> List[int]:
    """便捷函数：解析页面范围"""
    return PageRangeParser.parse_page_ranges(page_spec, total_pages)


def format_pages(pages: List[int]) -> str:
    """便捷函数：格式化页面范围"""
    return PageRangeParser.format_page_ranges(pages)
