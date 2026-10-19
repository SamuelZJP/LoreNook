/**
 * Reading font choices. Each choice is a list of named families tried in order; the browser
 * falls back per character, so a family missing on this device is skipped.
 *
 * Mixed text is resolved by putting the English list first: its families carry Latin glyphs only,
 * so Latin text takes the English choice and CJK characters fall through to the Chinese list. The
 * English lists therefore never include a generic or system-UI family (`serif`, `system-ui`,
 * `-apple-system`, …), which would claim CJK characters too.
 */
export type ZhFont = 'system' | 'song' | 'fangsong' | 'hei' | 'kai' | 'noto-serif'
export type EnFont = 'follow' | 'system' | 'serif' | 'sans' | 'mono'

const NOTO_SERIF = `'Source Han Serif SC', 'Noto Serif CJK SC', 'Noto Serif SC Variable', 'Noto Serif SC'`
const SONG = `'Songti SC', 'STSong', 'SimSun', 'NSimSun', 'AR PL UMing CN', ${NOTO_SERIF}`
const HEI = `'PingFang SC', 'Hiragino Sans GB', 'Heiti SC', 'STHeiti', 'Microsoft YaHei', 'SimHei', 'Source Han Sans SC', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei'`
/** Kaiti families, also used for chain-of-thought notes. */
export const KAI = `'Kaiti SC', 'STKaiti', 'KaiTi', 'KaiTi_GB2312', 'AR PL UKai CN'`

export const ZH_FONTS: { id: ZhFont; label: string; stack: string }[] = [
  { id: 'noto-serif', label: '思源宋体', stack: `${NOTO_SERIF}, 'Songti SC', 'STSong', 'Microsoft YaHei', 'PingFang SC', sans-serif` },
  { id: 'system', label: '系统默认', stack: `${HEI}, ${NOTO_SERIF}, sans-serif` },
  { id: 'song', label: '宋体', stack: `${SONG}, serif` },
  { id: 'fangsong', label: '仿宋', stack: `'FangSong', 'STFangsong', 'FangSong_GB2312', '仿宋', '仿宋_GB2312', 'FZFangSong-Z02S', ${SONG}, serif` },
  { id: 'hei', label: '黑体', stack: `'Heiti SC', 'STHeiti', 'SimHei', ${HEI}, sans-serif` },
  { id: 'kai', label: '楷体', stack: `${KAI}, '楷体', ${NOTO_SERIF}, serif` },
]

export const EN_FONTS: { id: EnFont; label: string; stack: string | null }[] = [
  { id: 'follow', label: '跟随中文字体', stack: null },
  { id: 'system', label: '系统默认', stack: `'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', 'Helvetica Neue', Arial` },
  { id: 'serif', label: '衬线', stack: `Georgia, 'Times New Roman', Times, 'Liberation Serif', 'DejaVu Serif', 'Noto Serif'` },
  { id: 'sans', label: '无衬线', stack: `'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', 'DejaVu Sans', 'Noto Sans'` },
  { id: 'mono', label: '等宽', stack: `'SF Mono', Menlo, Consolas, 'Cascadia Mono', 'Liberation Mono', 'DejaVu Sans Mono', 'Noto Sans Mono', 'Courier New'` },
]

function zhStack(id: ZhFont) {
  return (ZH_FONTS.find((f) => f.id === id) ?? ZH_FONTS[0]).stack
}
function enStack(id: EnFont) {
  return EN_FONTS.find((f) => f.id === id)?.stack ?? null
}

/** Font-family lists for body text and chain-of-thought notes. */
export function readingFonts(zh: ZhFont, en: EnFont): { reading: string; thought: string } {
  const lead = enStack(en)
  const prefix = lead ? `${lead}, ` : ''
  return {
    reading: `${prefix}${zhStack(zh)}`,
    thought: `${prefix}${KAI}, ${zhStack(zh)}`,
  }
}
