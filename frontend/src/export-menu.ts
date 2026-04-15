export interface ExportMenuItem {
  id: string;
  label: string;
  group: string;
  handler: () => void;
  enabled?: () => boolean;
}

export class ExportMenu {
  private btnEl: HTMLButtonElement;
  private menuEl: HTMLElement;
  private items: ExportMenuItem[];
  private isOpen = false;

  constructor(btnId: string, menuId: string, items: ExportMenuItem[]) {
    this.btnEl = document.getElementById(btnId) as HTMLButtonElement;
    this.menuEl = document.getElementById(menuId)!;
    this.items = items;

    this.render();
    this.btnEl.addEventListener("click", (e) => {
      e.stopPropagation();
      this.toggle();
    });
    this.btnEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        this.toggle();
      }
    });
    document.addEventListener("click", (e) => {
      if (this.isOpen && !this.menuEl.contains(e.target as Node) && e.target !== this.btnEl) {
        this.close();
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen) {
        this.close();
        this.btnEl.focus();
      }
    });
  }

  private render() {
    this.menuEl.setAttribute("role", "menu");
    this.menuEl.innerHTML = "";

    // Group items
    const groups = new Map<string, ExportMenuItem[]>();
    for (const item of this.items) {
      const arr = groups.get(item.group);
      if (arr) arr.push(item);
      else groups.set(item.group, [item]);
    }

    let first = true;
    for (const [groupName, groupItems] of groups) {
      if (!first) {
        const sep = document.createElement("div");
        sep.className = "export-menu-separator";
        sep.setAttribute("role", "separator");
        this.menuEl.appendChild(sep);
      }
      first = false;

      const label = document.createElement("div");
      label.className = "export-menu-group-label";
      label.textContent = groupName.charAt(0).toUpperCase() + groupName.slice(1);
      this.menuEl.appendChild(label);

      for (const item of groupItems) {
        const el = document.createElement("button");
        el.className = "export-menu-item";
        el.setAttribute("role", "menuitem");
        el.setAttribute("data-export-id", item.id);
        el.textContent = item.label;
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          item.handler();
          this.close();
        });
        this.menuEl.appendChild(el);
      }
    }
  }

  private toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }

  private open() {
    // Update enabled/disabled state
    for (const item of this.items) {
      const el = this.menuEl.querySelector(`[data-export-id="${item.id}"]`) as HTMLButtonElement | null;
      if (el) {
        const enabled = item.enabled ? item.enabled() : true;
        el.disabled = !enabled;
        el.classList.toggle("disabled", !enabled);
      }
    }

    this.menuEl.hidden = false;
    this.isOpen = true;

    // Focus first enabled item
    const firstEnabled = this.menuEl.querySelector(".export-menu-item:not(:disabled)") as HTMLElement | null;
    firstEnabled?.focus();

    // Keyboard nav within menu
    this.menuEl.addEventListener("keydown", this.handleMenuKeydown);
  }

  private close() {
    this.menuEl.hidden = true;
    this.isOpen = false;
    this.menuEl.removeEventListener("keydown", this.handleMenuKeydown);
  }

  private handleMenuKeydown = (e: KeyboardEvent) => {
    const menuItems = Array.from(
      this.menuEl.querySelectorAll<HTMLButtonElement>(".export-menu-item:not(:disabled)")
    );
    const current = document.activeElement as HTMLElement;
    const idx = menuItems.indexOf(current as HTMLButtonElement);

    switch (e.key) {
      case "ArrowDown": {
        e.preventDefault();
        const next = idx < menuItems.length - 1 ? idx + 1 : 0;
        menuItems[next].focus();
        break;
      }
      case "ArrowUp": {
        e.preventDefault();
        const prev = idx > 0 ? idx - 1 : menuItems.length - 1;
        menuItems[prev].focus();
        break;
      }
      case "Home":
        e.preventDefault();
        menuItems[0]?.focus();
        break;
      case "End":
        e.preventDefault();
        menuItems[menuItems.length - 1]?.focus();
        break;
    }
  };
}
