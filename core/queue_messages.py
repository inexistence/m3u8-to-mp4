"""任务队列的纯文案函数。"""
from __future__ import annotations


def scan_feedback(added: int, duplicates: int, unparseable: int, total: int) -> str:
    """返回单行扫描结果。"""
    return f'扫描完成：添加 {added}，重复 {duplicates}，无法解析 {unparseable}；共 {total} 个任务'


def conversion_feedback(done_count: int, total_count: int) -> str:
    """返回当前批次的单行转换状态。"""
    current = min(done_count + 1, total_count)
    return f'转换中：正在处理第 {current}/{total_count} 个任务'


def batch_feedback(success: int, failed: int, cancelled: int) -> str:
    """返回单行批次结果。"""
    message = f'本批完成：成功 {success}，失败 {failed}，取消 {cancelled}'
    if failed:
        return f'{message}；点击失败任务可查看详情'
    return message
