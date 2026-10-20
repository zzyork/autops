import { nextTick, type ObjectDirective } from 'vue'

const FOCUSABLE_FIELD = 'input:not([type="hidden"]):not(:disabled), textarea:not(:disabled), select:not(:disabled), button:not(:disabled), [tabindex]:not([tabindex="-1"])'

// Element Plus 的 Select 和 InputNumber 将这些属性留在外层，需同步给实际接收焦点的输入。
function syncNativeFieldAria(root: HTMLElement): void {
  const input = root.querySelector('input')
  if (!input) return
  for (const attribute of ['aria-invalid', 'aria-describedby', 'aria-labelledby']) {
    const value = root.getAttribute(attribute)
    if (value === null) input.removeAttribute(attribute)
    else input.setAttribute(attribute, value)
  }
}

export const vNativeFieldAria: ObjectDirective<HTMLElement> = {
  mounted: syncNativeFieldAria,
  updated: syncNativeFieldAria,
}

export function focusFormFeedback(root: HTMLElement | null): void {
  void nextTick(() => {
    if (!root?.isConnected) return
    const invalid = root.querySelector<HTMLElement>('[aria-invalid="true"], .field.is-error')
    const field = invalid?.matches(FOCUSABLE_FIELD) ? invalid : invalid?.querySelector<HTMLElement>(FOCUSABLE_FIELD)
    const target = field ?? root.querySelector<HTMLElement>('[data-form-error]')
    if (!target) return
    const region = field?.closest<HTMLElement>('.field') ?? invalid ?? target
    region.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    const feedbackId = field?.getAttribute('aria-describedby') ?? invalid?.getAttribute('aria-describedby')
    const feedback = feedbackId ? root.ownerDocument.getElementById(feedbackId) : null
    if (feedback && root.contains(feedback)) feedback.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    target.focus({ preventScroll: true })
  })
}
