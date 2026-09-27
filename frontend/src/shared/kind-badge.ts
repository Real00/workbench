import type { BadgeVariants } from '@/components/ui/badge'

/** Map domain kind keys to stock Badge variants. */
export function kindBadgeVariant(kind: string): NonNullable<BadgeVariants['variant']> {
  if (kind === 'blocker' || kind === 'risk') return 'destructive'
  if (kind === 'highlight') return 'default'
  if (kind === 'note') return 'outline'
  return 'secondary'
}
