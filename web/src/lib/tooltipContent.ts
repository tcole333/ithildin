/** Render research-supplied labels as text, never as HTML. */
export function setTooltipContent(element: HTMLElement | null, title: string, details: string[]): void {
  if (!element) return;
  const heading = document.createElement('strong');
  heading.textContent = title;
  element.replaceChildren(heading);
  for (const detail of details) {
    const line = document.createElement('div');
    line.textContent = detail;
    element.append(line);
  }
}
