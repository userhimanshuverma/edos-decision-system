export interface NavItem {
  id: string;
  label: string;
  href: string;
  disabled?: boolean;
  badge?: string;
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

export const navigationSections: NavSection[] = [
  {
    items: [
      {
        id: "overview",
        label: "Overview",
        href: "/",
      },
    ],
  },
  {
    title: "DECISIONS",
    items: [
      {
        id: "all-decisions",
        label: "All Decisions",
        href: "/decisions",
        disabled: true,
        badge: "Coming Soon",
      },
    ],
  },
  {
    title: "SUPPLY CHAIN",
    items: [
      {
        id: "products",
        label: "Products",
        href: "/supply-chain/products",
        disabled: true,
      },
      {
        id: "inventory",
        label: "Inventory",
        href: "/supply-chain/inventory",
        disabled: true,
      },
      {
        id: "suppliers",
        label: "Suppliers",
        href: "/supply-chain/suppliers",
        disabled: true,
      },
    ],
  },
  {
    title: "AUDIT",
    items: [
      {
        id: "audit-logs",
        label: "Audit Logs",
        href: "/audit",
        disabled: true,
      },
    ],
  },
];
