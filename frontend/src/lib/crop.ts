/** Pan-and-zoom cropping to a fixed frame: plain numbers, no DOM. */

export interface Size { w: number; h: number }
export interface Placement { x: number; y: number; scale: number }

/** Clamp a placement so the image always covers the frame. */
export function clampPlacement(image: Size, frame: Size, zoom: number, x: number, y: number): Placement {
  const scale = Math.max(frame.w / image.w, frame.h / image.h) * Math.max(1, zoom)
  const minX = frame.w - image.w * scale
  const minY = frame.h - image.h * scale
  return { scale, x: Math.min(0, Math.max(minX, x)), y: Math.min(0, Math.max(minY, y)) }
}

/** The centred placement for a zoom level. */
export function centred(image: Size, frame: Size, zoom: number): Placement {
  const scale = Math.max(frame.w / image.w, frame.h / image.h) * Math.max(1, zoom)
  return clampPlacement(image, frame, zoom, (frame.w - image.w * scale) / 2, (frame.h - image.h * scale) / 2)
}

/** Keep the frame centre fixed on the same image point while the zoom changes. */
export function rezoom(image: Size, frame: Size, from: Placement, zoom: number): Placement {
  const cx = (frame.w / 2 - from.x) / from.scale
  const cy = (frame.h / 2 - from.y) / from.scale
  const scale = Math.max(frame.w / image.w, frame.h / image.h) * Math.max(1, zoom)
  return clampPlacement(image, frame, zoom, frame.w / 2 - cx * scale, frame.h / 2 - cy * scale)
}

/** The source rectangle, in image pixels, that the frame shows. */
export function sourceRect(frame: Size, p: Placement): { sx: number; sy: number; sw: number; sh: number } {
  return { sx: -p.x / p.scale, sy: -p.y / p.scale, sw: frame.w / p.scale, sh: frame.h / p.scale }
}
