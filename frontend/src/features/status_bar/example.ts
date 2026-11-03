/** Starting code for a new status bar: every `世界` field as a label and value. */
export const EXAMPLE = `<style>
  .bar { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--page-muted); }
  .bar b { color: var(--page-text); font-weight: 600; margin-left: 4px; }
</style>
<div id="bar" class="bar"></div>
<script>
  lorenook.onData(({ state }) => {
    bar.replaceChildren(...Object.entries(state.世界 ?? {}).map(([key, value]) => {
      const item = document.createElement('span')
      const strong = document.createElement('b')
      strong.textContent = String(value)
      item.append(key, strong)
      return item
    }))
  })
</script>
`
