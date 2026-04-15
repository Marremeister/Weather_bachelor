export interface TabDef {
  id: string;
  label: string;
  panelId: string;
}

export interface TabControllerOptions {
  onSwitch?: (tabId: string) => void;
}

export class TabController {
  private navEl: HTMLElement;
  private tabs: TabDef[];
  private buttons: HTMLButtonElement[] = [];
  private panels: HTMLElement[] = [];
  private activeId: string;
  private onSwitch?: (tabId: string) => void;

  constructor(navId: string, tabs: TabDef[], options?: TabControllerOptions) {
    this.navEl = document.getElementById(navId)!;
    this.tabs = tabs;
    this.onSwitch = options?.onSwitch;
    this.activeId = tabs[0].id;

    this.init();
  }

  private init() {
    // Set ARIA on the nav container
    this.navEl.setAttribute("role", "tablist");

    for (const tab of this.tabs) {
      const btn = document.getElementById(`tab-${tab.id}`) as HTMLButtonElement;
      const panel = document.getElementById(tab.panelId)!;

      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-controls", tab.panelId);
      btn.setAttribute("aria-selected", tab.id === this.activeId ? "true" : "false");
      btn.setAttribute("tabindex", tab.id === this.activeId ? "0" : "-1");
      btn.id = `tab-${tab.id}`;

      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", `tab-${tab.id}`);
      panel.setAttribute("tabindex", "0");

      if (tab.id !== this.activeId) {
        panel.hidden = true;
      }

      btn.addEventListener("click", () => this.switchTo(tab.id));

      this.buttons.push(btn);
      this.panels.push(panel);
    }

    // Keyboard navigation on the tab bar
    this.navEl.addEventListener("keydown", (e) => this.handleKeydown(e));
  }

  private handleKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement;
    if (target.getAttribute("role") !== "tab") return;

    const idx = this.buttons.indexOf(target as HTMLButtonElement);
    if (idx === -1) return;

    let newIdx: number | null = null;

    switch (e.key) {
      case "ArrowRight":
        newIdx = (idx + 1) % this.buttons.length;
        break;
      case "ArrowLeft":
        newIdx = (idx - 1 + this.buttons.length) % this.buttons.length;
        break;
      case "Home":
        newIdx = 0;
        break;
      case "End":
        newIdx = this.buttons.length - 1;
        break;
      default:
        return;
    }

    e.preventDefault();
    this.buttons[newIdx].focus();
    this.switchTo(this.tabs[newIdx].id);
  }

  switchTo(tabId: string) {
    if (tabId === this.activeId) return;

    for (let i = 0; i < this.tabs.length; i++) {
      const isActive = this.tabs[i].id === tabId;
      this.buttons[i].setAttribute("aria-selected", isActive ? "true" : "false");
      this.buttons[i].setAttribute("tabindex", isActive ? "0" : "-1");
      this.buttons[i].classList.toggle("active", isActive);
      this.panels[i].hidden = !isActive;
    }

    this.activeId = tabId;
    this.onSwitch?.(tabId);
  }

  show() {
    this.navEl.hidden = false;
  }

  getActiveId(): string {
    return this.activeId;
  }
}
