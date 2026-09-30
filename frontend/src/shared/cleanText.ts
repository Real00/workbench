/**
 * 展示用文本清洗：抓取异常时后端存的可能是整页 HTML（Cloudflare 530 页等），
 * 且 last_error 只存前 N 字符，可能正好截断在未闭合标签中间。
 */
export function cleanText(value: string | null | undefined, fallback = '') {
  if (!value) return fallback
  const text = value
    .replace(/<[^>]*>/g, ' ')  // 完整标签
    .replace(/<[^>]*$/g, ' ')  // 截断后遗留的未闭合标签
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return fallback
  return text.length > 120 ? `${text.slice(0, 120)}…` : text
}
