/**
 * Which illustrated round the reader is on, from where each illustrated round's marker sits in
 * the scrolled timeline. Plain numbers in, a round id out.
 */
export interface Mark { roundId: string; top: number }

/**
 * `marks` are in round order with `top` measured from the top of the visible area. The reader is
 * on the last round whose marker has passed the reading line; above every marker, on the first;
 * at the very end of the timeline, on the last, even when its marker sits below the line.
 */
export function pickReadingRound(marks: Mark[], line: number, atEnd: boolean): string | null {
  if (!marks.length) return null
  if (atEnd) return marks[marks.length - 1].roundId
  let current = marks[0].roundId
  for (const mark of marks) if (mark.top <= line) current = mark.roundId
  return current
}
