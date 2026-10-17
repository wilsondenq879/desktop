/* Full text is already visible in touch/narrow layouts: no sticky Tippy
 * bubble needed. Do not intercept question clicks or change submit settings.
 */
(() => {
  if (window.__openwebuiMobileFollowups) return;
  window.__openwebuiMobileFollowups = true;
  const mobile = matchMedia('(max-width: 767px), (hover: none) and (pointer: coarse)');
  const disabledByUs = new WeakSet();
  const selector = '.flex.flex-col.text-left.gap-1 > .line-clamp-1';
  let scheduled = false;
  const update = () => {
    scheduled = false;
    document.querySelectorAll(selector).forEach(wrapper => {
      if (!wrapper.querySelector(':scope > button[aria-label] > .line-clamp-1')) return;
      const tooltip = wrapper._tippy;
      if (!tooltip || tooltip.state.isDestroyed) return;
      if (mobile.matches && tooltip.state.isEnabled) {
        disabledByUs.add(tooltip);
        tooltip.disable();
      } else if (!mobile.matches && disabledByUs.has(tooltip)) {
        disabledByUs.delete(tooltip);
        tooltip.enable();
      }
    });
  };
  const schedule = () => {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(update);
    }
  };
  const start = () => {
    new MutationObserver(schedule).observe(document.body, {childList:true, subtree:true});
    mobile.addEventListener('change', schedule);
    update();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
