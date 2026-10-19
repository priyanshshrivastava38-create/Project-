export const NAV_GROUPS = [
  { label: 'Overview', items: [
    { to: '/dashboard', label: 'Dashboard', icon: 'dashboard', perm: 'dashboard:read' },
    { to: '/assistant', label: 'Assistant', icon: 'assistant', perm: 'assistant:use' },
  ] },
  { label: 'Sales', items: [
    { to: '/customers', label: 'Customers', icon: 'customers', perm: 'customers:read' },
    { to: '/orders', label: 'Orders', icon: 'orders', perm: 'orders:read' },
  ] },
  { label: 'Operations', items: [
    { to: '/inventory', label: 'Inventory', icon: 'inventory', perm: 'inventory:read' },
    { to: '/production', label: 'Production', icon: 'production', perm: 'production:read' },
    { to: '/quality', label: 'Quality', icon: 'quality', perm: 'quality:read' },
    { to: '/deliveries', label: 'Deliveries', icon: 'deliveries', perm: 'deliveries:read' },
  ] },
  { label: 'Purchasing', items: [
    { to: '/suppliers', label: 'Suppliers', icon: 'suppliers', perm: 'suppliers:read' },
  ] },
  { label: 'Knowledge', items: [
    { to: '/documents', label: 'Documents', icon: 'documents', perm: 'documents:read' },
  ] },
  { label: 'Insights', items: [
    { to: '/reports', label: 'Reports', icon: 'reports', perm: 'reports:read' },
  ] },
  { label: 'Admin', items: [
    { to: '/admin/users', label: 'Users', icon: 'users', perm: 'users:manage' },
    { to: '/admin/audit', label: 'Audit log', icon: 'audit', perm: 'audit:read' },
  ] },
];

export function firstAllowedPath(can) {
  for (const g of NAV_GROUPS) {
    for (const i of g.items) if (can(i.perm)) return i.to;
  }
  return '/no-access';
}
