import { createAvatar } from '@dicebear/core'
import * as pixelArt from '@dicebear/pixel-art'
import type { Options } from '@dicebear/pixel-art'

export function clothingHex(color: string | null | undefined) {
  const raw = (color ?? '#36d9e9').replace('#', '').toLowerCase()
  return /^[0-9a-f]{6}$/.test(raw) ? raw : '36d9e9'
}

export function memberHasDeskWork(taskCount: number) {
  return taskCount > 0
}

export const deskHair: NonNullable<Options['hair']> = [
  'short01', 'short02', 'short06', 'short08', 'short09', 'short10', 'short11',
  'short14', 'short15', 'short16', 'short17', 'short19', 'short22',
  'long01', 'long02', 'long03', 'long04', 'long05', 'long07', 'long08', 'long09',
  'long11', 'long12', 'long13', 'long14', 'long15', 'long16', 'long17', 'long18',
  'long19', 'long20', 'long21',
]

const hairColor = [
  '28150a', '3d2314', '603a14', '83623b', 'a78961', '611c17', '1a1210', '4a3728',
]

export function memberPixelUri(seed: string, color?: string | null) {
  return createAvatar(pixelArt, {
    seed,
    size: 80,
    scale: 100,
    radius: 0,
    clothingColor: [clothingHex(color)],
    hair: deskHair,
    hairColor,
    backgroundColor: ['transparent'],
    hatProbability: 0,
    accessoriesProbability: 0,
  }).toDataUri()
}
