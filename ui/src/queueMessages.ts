export function batchFeedback(success: number, failed: number, cancelled: number): string {
  const message = `本批完成：成功 ${success}，失败 ${failed}，取消 ${cancelled}`
  return failed ? `${message}；点击失败任务可查看详情` : message
}
