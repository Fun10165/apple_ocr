"""
页面范围解析器的单元测试
"""

import pytest
from apple_ocr.page_parser import PageRangeParser, parse_pages, format_pages


class TestPageRangeParser:
    """页面范围解析器测试"""

    def test_parse_single_pages(self):
        """测试单页解析"""
        # 测试单页
        result = parse_pages("1", 10)
        assert result == [0]  # 0-based
        
        result = parse_pages("5", 10)
        assert result == [4]
        
        # 测试多个单页
        result = parse_pages("1,3,5", 10)
        assert result == [0, 2, 4]

    def test_parse_ranges(self):
        """测试范围解析"""
        # 测试简单范围
        result = parse_pages("1-3", 10)
        assert result == [0, 1, 2]
        
        result = parse_pages("5-8", 10)
        assert result == [4, 5, 6, 7]

    def test_parse_mixed(self):
        """测试混合格式"""
        result = parse_pages("1,3,5-7,10", 15)
        assert result == [0, 2, 4, 5, 6, 9]
        
        # 测试复杂混合
        result = parse_pages("1-3,5,8-10,15", 20)
        assert result == [0, 1, 2, 4, 7, 8, 9, 14]

    def test_parse_empty_or_none(self):
        """测试空输入"""
        # 空字符串应返回所有页面
        result = parse_pages("", 5)
        assert result == [0, 1, 2, 3, 4]
        
        result = parse_pages("   ", 3)
        assert result == [0, 1, 2]

    def test_parse_errors(self):
        """测试错误情况"""
        # 页面号超出范围
        with pytest.raises(ValueError, match="页面号超出范围"):
            parse_pages("15", 10)
        
        # 页面号小于1
        with pytest.raises(ValueError, match="页面号必须大于0"):
            parse_pages("0", 10)
        
        # 范围格式错误
        with pytest.raises(ValueError, match="无效的页面范围格式"):
            parse_pages("1-", 10)
        
        with pytest.raises(ValueError, match="无效的页面范围格式"):
            parse_pages("1-2-3", 10)
        
        # 起始页大于结束页
        with pytest.raises(ValueError, match="起始页面不能大于结束页面"):
            parse_pages("5-3", 10)
        
        # 无效格式
        with pytest.raises(ValueError, match="无效的页面号格式"):
            parse_pages("abc", 10)

    def test_format_pages(self):
        """测试页面格式化"""
        # 测试单页
        result = format_pages([0])
        assert result == "1"
        
        result = format_pages([0, 2, 4])
        assert result == "1,3,5"
        
        # 测试连续范围
        result = format_pages([0, 1, 2])
        assert result == "1-3"
        
        result = format_pages([4, 5, 6, 7])
        assert result == "5-8"
        
        # 测试混合
        result = format_pages([0, 2, 4, 5, 6, 9])
        assert result == "1,3,5-7,10"
        
        # 测试空列表
        result = format_pages([])
        assert result == ""

    def test_round_trip(self):
        """测试解析和格式化的往返转换"""
        test_cases = [
            "1",
            "1,3,5",
            "1-5",
            "1,3,5-7,10",
            "1-3,5,8-10,15"
        ]
        
        for case in test_cases:
            parsed = parse_pages(case, 20)
            formatted = format_pages(parsed)
            reparsed = parse_pages(formatted, 20)
            assert parsed == reparsed, f"Round trip failed for: {case}"

    def test_edge_cases(self):
        """测试边界情况"""
        # 单页PDF
        result = parse_pages("1", 1)
        assert result == [0]
        
        # 最后一页
        result = parse_pages("10", 10)
        assert result == [9]
        
        # 全范围
        result = parse_pages("1-10", 10)
        assert result == list(range(10))
        
        # 重复页面应去重
        result = parse_pages("1,1,2,2", 10)
        assert result == [0, 1]

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        result = parse_pages(" 1 , 3 , 5-7 ", 10)
        assert result == [0, 2, 4, 5, 6]
        
        result = parse_pages("1,  ,3", 10)
        assert result == [0, 2]