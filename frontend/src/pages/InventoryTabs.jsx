import { Tabs } from '../components';
import { useAuth } from '../context/AuthContext';

export default function InventoryTabs() {
  const { can } = useAuth();
  const tabs = [
    { value: 'stock', label: 'Stock levels', to: '/inventory' },
    can('products:read') ? { value: 'materials', label: 'Materials', to: '/inventory/materials' } : null,
    { value: 'txns', label: 'Transactions', to: '/inventory/transactions' },
  ].filter(Boolean);
  return <Tabs tabs={tabs} />;
}
